import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any, AsyncIterable, Dict, List, Optional, Sequence

from tenacity import retry, stop_after_attempt, wait_fixed

if sys.version_info >= (3, 11):
    from asyncio import TaskGroup
else:
    from taskgroup import TaskGroup

from .exceptions import PipelineError, StageValidationError
from .tracker import StatusEvent, StatusTracker
from .types import (
    DashboardSnapshot,
    PipelineStats,
    TaskEvent,
    TaskFunc,
    WorkerMetrics,
    WorkerState,
)
from .utils import extract_exception, setup_logger

logger = setup_logger(__name__)


@dataclass
class Stage:
    """
    A stage in the pipeline that processes items through a sequence of tasks.
    """
    name: str
    workers: int
    tasks: Sequence[TaskFunc]
    retry: str = "per_task"
    task_attempts: int = 3
    task_wait_seconds: float = 1.0
    stage_attempts: int = 3
    unpack_args: bool = False

    def validate(self) -> None:
        """
        Validate stage configuration.

        Raises:
            StageValidationError: If configuration is invalid
        """
        if self.retry not in ("per_task", "per_stage"):
            raise StageValidationError(
                f"Invalid retry policy for stage '{self.name}': {self.retry}. "
                f"Must be 'per_task' or 'per_stage'"
            )
        if self.workers < 1:
            raise StageValidationError(
                f"Stage '{self.name}' must have at least 1 worker, got {self.workers}"
            )
        if not self.tasks:
            raise StageValidationError(
                f"Stage '{self.name}' must have at least one task"
            )
        if self.task_attempts < 1:
            raise StageValidationError(
                f"Stage '{self.name}' task_attempts must be at least 1, got {self.task_attempts}"
            )
        if self.stage_attempts < 1:
            raise StageValidationError(
                f"Stage '{self.name}' stage_attempts must be at least 1, got {self.stage_attempts}"
            )


class Pipeline:
    """
    A multi-stage async pipeline with worker pools and flexible retry strategies.
    """

    def __init__(
        self,
        stages: List[Stage],
        collect_results: bool = True,
        status_tracker: Optional[StatusTracker] = None
    ):
        """
        Initialize the pipeline.

        Args:
            stages: List of Stage objects defining the pipeline
            collect_results: If True, collect results from final stage
            status_tracker: Optional StatusTracker for monitoring item status

        Raises:
            PipelineError: If stages list is empty
            StageValidationError: If any stage configuration is invalid
        """
        if not stages:
            raise PipelineError("Pipeline must have at least one stage")

        for stage in stages:
            stage.validate()

        self.stages = stages
        self.collect_results = collect_results
        self._status_tracker = status_tracker

        self._stop_event = asyncio.Event()
        self._queues: List[asyncio.Queue] = [asyncio.Queue() for _ in stages]
        self._results: List[Dict[str, Any]] = []
        self._sequence_counter = 0
        self._items_processed = 0
        self._items_failed = 0
        self._worker_tasks: List[asyncio.Task] = []
        self._shutdown = False

        self._worker_states: Dict[str, WorkerState] = {}
        self._worker_metrics: Dict[str, WorkerMetrics] = {}
        self._initialize_worker_tracking()

    @property
    def results(self) -> List[Dict[str, Any]]:
        """Get collected results, sorted by sequence."""
        return sorted(self._results, key=lambda x: x.get("_sequence_id", 0))

    def get_stats(self) -> PipelineStats:
        """
        Get current pipeline statistics.

        Returns:
            PipelineStats with current metrics
        """
        queue_sizes = {
            stage.name: self._queues[i].qsize()
            for i, stage in enumerate(self.stages)
        }

        items_in_flight = sum(queue_sizes.values())

        return PipelineStats(
            items_processed=self._items_processed,
            items_failed=self._items_failed,
            items_in_flight=items_in_flight,
            queue_sizes=queue_sizes
        )

    def get_worker_names(self) -> Dict[str, List[str]]:
        """
        Get all worker names organized by stage.

        Useful for tracking which workers exist before pipeline runs.

        Returns:
            Dictionary mapping stage name to list of worker names

        Example:

            ```python
            pipeline = Pipeline(stages=[
                Stage(name="Fetch", workers=3, tasks=[fetch]),
                Stage(name="Process", workers=2, tasks=[process])
            ])
            pipeline.get_worker_names()
            # {
            #     "Fetch": ["Fetch-W0", "Fetch-W1", "Fetch-W2"],
            #     "Process": ["Process-W0", "Process-W1"]
            # }
            ```
        """
        worker_names = {}
        for stage in self.stages:
            worker_names[stage.name] = [
                f"{stage.name}-W{i}" for i in range(stage.workers)
            ]
        return worker_names

    def _initialize_worker_tracking(self) -> None:
        """Initialize worker state and metrics tracking."""
        for stage in self.stages:
            for i in range(stage.workers):
                worker_name = f"{stage.name}-W{i}"

                self._worker_states[worker_name] = WorkerState(
                    worker_name=worker_name,
                    stage=stage.name,
                    status="idle"
                )

                self._worker_metrics[worker_name] = WorkerMetrics(
                    worker_name=worker_name,
                    stage=stage.name
                )

    def get_worker_states(self) -> Dict[str, WorkerState]:
        """
        Get current state of all workers.

        Returns:
            Dictionary mapping worker name to WorkerState

        Example:
            ```python
            states = pipeline.get_worker_states()
            for name, state in states.items():
                if state.status == "busy":
                    print(f"{name} processing item {state.current_item_id}")
            ```
        """
        return dict(self._worker_states)

    def get_worker_metrics(self) -> Dict[str, WorkerMetrics]:
        """
        Get performance metrics for all workers.

        Returns:
            Dictionary mapping worker name to WorkerMetrics

        Example:
            ```python
            metrics = pipeline.get_worker_metrics()
            for name, metric in metrics.items():
                print(f"{name}: {metric.items_processed} items, "
                      f"avg {metric.avg_processing_time:.2f}s")
            ```
        """
        return dict(self._worker_metrics)

    def get_dashboard_snapshot(self) -> DashboardSnapshot:
        """
        Get complete dashboard snapshot with all current state.

        Returns:
            DashboardSnapshot with worker states, metrics, and pipeline stats

        Example:
            ```python
            snapshot = pipeline.get_dashboard_snapshot()
            print(f"Active workers: {sum(1 for s in snapshot.worker_states.values() if s.status == 'busy')}")
            print(f"Items processed: {snapshot.pipeline_stats.items_processed}")
            ```
        """
        return DashboardSnapshot(
            worker_states=self.get_worker_states(),
            worker_metrics=self.get_worker_metrics(),
            pipeline_stats=self.get_stats(),
            timestamp=time.time()
        )

    async def feed(self, items: Sequence[Any]) -> None:
        """
        Feed items into the first stage of the pipeline.

        Args:
            items: Sequence of items to process
        """
        q0 = self._queues[0]
        first_stage_name = self.stages[0].name if self.stages else None
        for item in items:
            payload = self._prepare_payload(item)
            await q0.put((payload, 1))
            logger.debug(f"Enqueued item id={payload['id']}")
            await self._emit_status(
                payload['id'],
                first_stage_name,
                "queued"
            )

    async def feed_async(self, items: AsyncIterable[Any]) -> None:
        """
        Feed items from an async iterable into the first stage.

        Args:
            items: Async iterable of items to process
        """
        q0 = self._queues[0]
        first_stage_name = self.stages[0].name if self.stages else None
        async for item in items:
            payload = self._prepare_payload(item)
            await q0.put((payload, 1))
            logger.debug(f"Enqueued item id={payload['id']}")
            await self._emit_status(
                payload['id'],
                first_stage_name,
                "queued"
            )

    def _prepare_payload(self, item: Any) -> Dict[str, Any]:
        """
        Prepare an item as a payload dict with sequence tracking.

        Args:
            item: Input item (can be dict with custom "id" field)

        Returns:
            Payload dictionary
        """
        if isinstance(item, dict) and "id" in item:
            payload = {
                "id": item["id"],
                "value": item.get("value", item),
                "_sequence_id": self._sequence_counter
            }
            for k, v in item.items():
                payload.setdefault(k, v)
        else:
            payload = {
                "id": self._sequence_counter,
                "value": item,
                "_sequence_id": self._sequence_counter
            }

        self._sequence_counter += 1
        return payload

    async def run(self, items: Sequence[Any]) -> List[Dict[str, Any]]:
        """
        Run the pipeline end-to-end with the given items.

        Args:
            items: Items to process through the pipeline

        Returns:
            List of result dictionaries
        """
        await self.feed(items)

        async with TaskGroup() as tg:
            for stage_index, stage in enumerate(self.stages):
                name_prefix = stage.name
                input_q = self._queues[stage_index]
                output_q = (
                    self._queues[stage_index + 1]
                    if stage_index + 1 < len(self._queues)
                    else None
                )

                for i in range(stage.workers):
                    worker_name = f"{name_prefix}-W{i}"
                    task = tg.create_task(
                        self._stage_worker(worker_name, stage_index, stage, input_q, output_q)
                    )
                    self._worker_tasks.append(task)

            for q in self._queues:
                await q.join()

            self._stop_event.set()

        return self.results

    async def add_stage(self, stage: Stage, position: Optional[int] = None) -> None:
        """
        Add a stage to the pipeline dynamically.

        Args:
            stage: Stage to add
            position: Position to insert at (None = append to end)

        Raises:
            StageValidationError: If stage configuration is invalid
            PipelineError: If pipeline is currently running
        """
        if self._worker_tasks:
            raise PipelineError("Cannot add stages while pipeline is running")

        stage.validate()

        if position is None:
            self.stages.append(stage)
            self._queues.append(asyncio.Queue())
        else:
            self.stages.insert(position, stage)
            self._queues.insert(position, asyncio.Queue())

        for i in range(stage.workers):
            worker_name = f"{stage.name}-W{i}"

            self._worker_states[worker_name] = WorkerState(
                worker_name=worker_name,
                stage=stage.name,
                status="idle"
            )

            self._worker_metrics[worker_name] = WorkerMetrics(
                worker_name=worker_name,
                stage=stage.name
            )

        logger.info(f"Added stage '{stage.name}' at position {position or len(self.stages)-1}")

    async def remove_stage(self, name: str) -> None:
        """
        Remove a stage from the pipeline by name.

        Args:
            name: Name of the stage to remove

        Raises:
            PipelineError: If stage not found or pipeline is running
        """
        if self._worker_tasks:
            raise PipelineError("Cannot remove stages while pipeline is running")

        for i, stage in enumerate(self.stages):
            if stage.name == name:
                for j in range(stage.workers):
                    worker_name = f"{stage.name}-W{j}"
                    self._worker_states.pop(worker_name, None)
                    self._worker_metrics.pop(worker_name, None)

                self.stages.pop(i)
                self._queues.pop(i)
                logger.info(f"Removed stage '{name}'")
                return

        raise PipelineError(f"Stage '{name}' not found")

    async def shutdown(self) -> None:
        """Shut down the pipeline gracefully."""
        if self._shutdown:
            return

        logger.debug("Shutting down pipeline")
        self._shutdown = True
        self._stop_event.set()

        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        logger.debug("Pipeline shutdown complete")

    async def __aenter__(self) -> "Pipeline":
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with automatic shutdown."""
        await self.shutdown()

    async def _emit_status(
        self,
        item_id: Any,
        stage: str | None,
        status: str,
        worker: str | None = None,
        metadata: Dict[str, Any] | None = None
    ) -> None:
        """
        Emit status event if tracker is configured.

        Args:
            item_id: Item identifier
            stage: Stage name
            status: Status type
            worker: Worker name (optional)
            metadata: Additional metadata (optional)
        """
        if self._status_tracker:
            event = StatusEvent(
                item_id=item_id,
                stage=stage,
                status=status,
                worker=worker,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            await self._status_tracker._emit(event)

    async def _emit_task_event(
        self,
        item_id: Any,
        stage: str,
        task_name: str,
        worker: str,
        event_type: str,
        attempt: int,
        error: Optional[Exception] = None,
        duration: Optional[float] = None
    ) -> None:
        """
        Emit task-level event if tracker is configured.

        Args:
            item_id: Item identifier
            stage: Stage name
            task_name: Task function name
            worker: Worker name
            event_type: Type of event (start, complete, retry, fail)
            attempt: Current attempt number
            error: Exception if task failed or is retrying
            duration: Time taken to execute task in seconds
        """
        if self._status_tracker:
            event = TaskEvent(
                item_id=item_id,
                stage=stage,
                task_name=task_name,
                worker=worker,
                event_type=event_type,
                attempt=attempt,
                timestamp=time.time(),
                error=error,
                duration=duration
            )
            await self._status_tracker._emit_task_event(event)

    async def _stage_worker(
        self,
        name: str,
        stage_index: int,
        stage: Stage,
        input_q: asyncio.Queue,
        output_q: Optional[asyncio.Queue],
    ) -> None:
        """
        Worker loop for a single stage.

        Args:
            name: Worker name
            stage_index: Index of this stage
            stage: Stage configuration
            input_q: Input queue
            output_q: Output queue (None for final stage)
        """
        while not self._stop_event.is_set() or not input_q.empty():
            try:
                payload, attempt = await asyncio.wait_for(input_q.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            item_id = payload.get("id")
            start_time = time.time()

            self._worker_states[name].status = "busy"
            self._worker_states[name].current_item_id = item_id
            self._worker_states[name].processing_since = start_time

            try:
                logger.debug(f"[{name}] START stage={stage.name} id={item_id} attempt={attempt}")

                await self._emit_status(
                    item_id,
                    stage.name,
                    "in_progress",
                    worker=name
                )

                if stage.retry == "per_task":
                    result_value = await self._run_per_task(
                        stage, payload["value"], name, item_id
                    )
                else:
                    result_value = await self._run_per_stage(
                        stage, payload["value"], name, item_id, payload, attempt, input_q
                    )
                    if result_value is None:
                        continue

                payload["value"] = result_value

                await self._emit_status(
                    item_id,
                    stage.name,
                    "completed",
                    worker=name
                )

                if output_q is not None:
                    await output_q.put((payload, 1))
                    is_not_last_stage = stage_index + 1 < len(self.stages)
                    next_stage_name = (
                        self.stages[stage_index + 1].name if is_not_last_stage else None
                    )
                    if next_stage_name:
                        await self._emit_status(
                            item_id,
                            next_stage_name,
                            "queued"
                        )
                else:
                    if self.collect_results:
                        self._results.append({**payload})

                self._items_processed += 1
                logger.debug(f"[{name}] END stage={stage.name} id={item_id}")

                processing_time = time.time() - start_time
                self._worker_metrics[name].items_processed += 1
                self._worker_metrics[name].total_processing_time += processing_time
                self._worker_metrics[name].last_active = time.time()

            except Exception as e:
                original_error = extract_exception(e)
                logger.error(
                    f"[{name}] FAIL stage={stage.name} id={item_id} error={original_error}"
                )
                self._items_failed += 1

                processing_time = time.time() - start_time
                self._worker_metrics[name].items_failed += 1
                self._worker_metrics[name].total_processing_time += processing_time
                self._worker_metrics[name].last_active = time.time()

                await self._emit_status(
                    item_id,
                    stage.name,
                    "failed",
                    metadata={"error": str(original_error)}
                )
            finally:
                self._worker_states[name].status = "idle"
                self._worker_states[name].current_item_id = None
                self._worker_states[name].processing_since = None
                input_q.task_done()

    async def _run_per_task(
        self,
        stage: Stage,
        value: Any,
        worker_name: str,
        item_id: Any,
    ) -> Any:
        """
        Execute stage tasks with per-task retry strategy.

        Args:
            stage: Stage configuration
            value: Input value
            worker_name: Name of the worker
            item_id: Item identifier

        Returns:
            Final processed value

        Raises:
            RetryError: If a task exhausts its retries
        """
        current = value

        for idx, task in enumerate(stage.tasks):
            task_name = task.__name__
            wrapped = self._wrap_with_tenacity(
                task, stage, worker_name, item_id, task_name
            )

            logger.debug(
                f"[{worker_name}] START task {idx+1}/{len(stage.tasks)}={task_name} id={item_id}"
            )

            try:
                if stage.unpack_args:
                    if isinstance(current, dict):
                        current = await wrapped(**current)
                    elif isinstance(current, (list, tuple)):
                        current = await wrapped(*current)
                    else:
                        current = await wrapped(current)
                else:
                    current = await wrapped(current)

                logger.debug(
                    f"[{worker_name}] END task {idx+1}/{len(stage.tasks)}={task_name} id={item_id}"
                )

            except Exception as e:
                original_error = extract_exception(e)
                logger.error(
                    f"[{worker_name}] FAIL task={task_name} id={item_id} error={original_error}"
                )

                raise

        return current

    async def _run_per_stage(
        self,
        stage: Stage,
        value: Any,
        worker_name: str,
        item_id: Any,
        payload: Dict[str, Any],
        attempt: int,
        input_q: asyncio.Queue,
    ) -> Optional[Any]:
        """
        Execute stage tasks with per-stage retry strategy.

        Args:
            stage: Stage configuration
            value: Input value
            worker_name: Worker name
            item_id: Item identifier
            payload: Full payload dict
            attempt: Current attempt number
            input_q: Input queue for re-queueing

        Returns:
            Final value if successful, None if retried or failed
        """
        current = value

        try:
            for idx, task in enumerate(stage.tasks):
                task_name = task.__name__

                logger.debug(
                    f"[{worker_name}] START task {idx+1}/{len(stage.tasks)}="
                    f"{task_name} id={item_id}"
                )

                if stage.unpack_args:
                    if isinstance(current, dict):
                        current = await task(**current)
                    elif isinstance(current, (list, tuple)):
                        current = await task(*current)
                    else:
                        current = await task(current)
                else:
                    current = await task(current)

                logger.debug(
                    f"[{worker_name}] END task {idx+1}/{len(stage.tasks)}={task_name} id={item_id}"
                )

            return current

        except Exception as e:
            original_error = extract_exception(e)

            if attempt < stage.stage_attempts:
                logger.debug(
                    f"[{worker_name}] RETRY stage={stage.name} id={item_id} "
                    f"attempt={attempt} error={original_error}"
                )

                await input_q.put((payload, attempt + 1))

                await self._emit_status(
                    item_id,
                    stage.name,
                    "queued",
                    metadata={"attempt": attempt + 1, "retry": True}
                )

                return None
            else:
                logger.error(
                    f"[{worker_name}] FAIL stage={stage.name} id={item_id} "
                    f"after {attempt} attempts error={original_error}"
                )

                self._items_failed += 1

                await self._emit_status(
                    item_id,
                    stage.name,
                    "failed",
                    metadata={"error": str(original_error)}
                )

                return None

    def _wrap_with_tenacity(
        self,
        task: TaskFunc,
        stage: Stage,
        worker_name: str,
        item_id: Any,
        task_name: str,
    ) -> TaskFunc:
        """
        Wrap a task with tenacity retry logic and callbacks.

        Args:
            task: Task to wrap
            stage: Stage configuration
            worker_name: Worker name
            item_id: Item identifier
            task_name: Task name

        Returns:
            Wrapped task function
        """
        attempt_counter = {"count": 0}

        @retry(
            stop=stop_after_attempt(stage.task_attempts),
            wait=wait_fixed(stage.task_wait_seconds)
        )
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            attempt_counter["count"] += 1
            current_attempt = attempt_counter["count"]
            start_time = time.time()

            await self._emit_task_event(
                item_id=item_id,
                stage=stage.name,
                task_name=task_name,
                worker=worker_name,
                event_type="start",
                attempt=current_attempt
            )

            try:
                result = await task(*args, **kwargs)
                duration = time.time() - start_time

                await self._emit_task_event(
                    item_id=item_id,
                    stage=stage.name,
                    task_name=task_name,
                    worker=worker_name,
                    event_type="complete",
                    attempt=current_attempt,
                    duration=duration
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                if current_attempt < stage.task_attempts:
                    logger.debug(
                        f"[{worker_name}] RETRY task={task_name} id={item_id} "
                        f"attempt={current_attempt} error={e}"
                    )

                    await self._emit_task_event(
                        item_id=item_id,
                        stage=stage.name,
                        task_name=task_name,
                        worker=worker_name,
                        event_type="retry",
                        attempt=current_attempt,
                        error=e,
                        duration=duration
                    )
                else:
                    await self._emit_task_event(
                        item_id=item_id,
                        stage=stage.name,
                        task_name=task_name,
                        worker=worker_name,
                        event_type="fail",
                        attempt=current_attempt,
                        error=e,
                        duration=duration
                    )

                raise

        return wrapped
