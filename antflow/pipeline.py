import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, Sequence

from tenacity import retry, stop_after_attempt, wait_fixed

if sys.version_info >= (3, 11):
    from asyncio import TaskGroup
else:
    from taskgroup import TaskGroup

from .exceptions import PipelineError, StageValidationError
from .tracker import StatusEvent, StatusTracker
from .types import (
    DashboardSnapshot,
    PipelineResult,
    PipelineStats,
    StageStats,
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
    task_concurrency_limits: Dict[str, int] = field(default_factory=dict)
    on_success: Optional[Callable[[Any, Any, Dict[str, Any]], Any]] = None
    on_failure: Optional[Callable[[Any, Exception, Dict[str, Any]], Any]] = None
    skip_if: Optional[Callable[[Any], bool]] = None
    queue_capacity: Optional[int] = None

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
            raise StageValidationError(f"Stage '{self.name}' must have at least one task")
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
        status_tracker: Optional[StatusTracker] = None,
    ):
        """
        Initialize the pipeline.

        Args:
            stages: List of Stage objects defining the pipeline
            collect_results: If True, collects results from the final stage into `self.results`.
                If False, results are discarded after processing (useful for fire-and-forget or side-effect only pipelines).
                Defaults to True.
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
        self._queues: List[asyncio.PriorityQueue] = []
        for stage in stages:
            if stage.queue_capacity is not None:
                maxsize = stage.queue_capacity
            else:
                # Smart Default: Buffer size based on worker count
                # Factor of 10 allows for some buffering but prevents infinite growth
                maxsize = max(1, stage.workers * 10)
            
            self._queues.append(asyncio.PriorityQueue(maxsize=maxsize))
        self._msg_counter = 0
        self._results: List[PipelineResult] = []
        self._sequence_counter = 0
        self._items_processed = 0
        self._items_failed = 0
        self._worker_tasks: List[asyncio.Task] = []
        self._runner_task: Optional[asyncio.Task] = None
        self._shutdown = False

        self._worker_states: Dict[str, WorkerState] = {}
        self._worker_metrics: Dict[str, WorkerMetrics] = {}
        self._task_semaphores: Dict[str, Dict[str, asyncio.Semaphore]] = {}
        self._initialize_worker_tracking()
        self._initialize_semaphores()

    @property
    def results(self) -> List[PipelineResult]:
        """
        Get collected results, sorted by original input sequence.

        Only contains data if `collect_results=True` was passed to `__init__`.
        """
        return sorted(self._results, key=lambda x: x.sequence_id)

    def get_stats(self) -> PipelineStats:
        """
        Get current pipeline statistics.

        Returns:
            [PipelineStats][antflow.types.PipelineStats] with current metrics
        """
        queue_sizes = {}
        stage_stats = {}
        
        # Calculate aggregations
        worker_states = self.get_worker_states().values()
        worker_metrics_all = self.get_worker_metrics().values()

        for i, stage in enumerate(self.stages):
            # Pending
            pending = self._queues[i].qsize()
            queue_sizes[stage.name] = pending
            
            # In Progress (Busy Workers)
            in_progress = sum(
                1 for s in worker_states 
                if s.stage == stage.name and s.status == "busy"
            )
            
            # Completed/Failed (by workers in this stage)
            completed = sum(
                m.items_processed for m in worker_metrics_all 
                if m.stage == stage.name
            )
            failed = sum(
                m.items_failed for m in worker_metrics_all 
                if m.stage == stage.name
            )
            
            stage_stats[stage.name] = StageStats(
                stage_name=stage.name,
                pending_items=pending,
                in_progress_items=in_progress,
                completed_items=completed,
                failed_items=failed
            )

        items_in_flight = sum(s.pending_items + s.in_progress_items for s in stage_stats.values())

        return PipelineStats(
            items_processed=self._items_processed,
            items_failed=self._items_failed,
            items_in_flight=items_in_flight,
            queue_sizes=queue_sizes,
            stage_stats=stage_stats,
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
            worker_names[stage.name] = [f"{stage.name}-W{i}" for i in range(stage.workers)]
        return worker_names

    def _initialize_worker_tracking(self) -> None:
        """Initialize worker state and metrics tracking."""
        for stage in self.stages:
            for i in range(stage.workers):
                worker_name = f"{stage.name}-W{i}"

                self._worker_states[worker_name] = WorkerState(
                    worker_name=worker_name, stage=stage.name, status="idle"
                )

                self._worker_metrics[worker_name] = WorkerMetrics(
                    worker_name=worker_name, stage=stage.name
                )

    def _initialize_semaphores(self) -> None:
        """Initialize semaphores for task concurrency limits."""
        for stage in self.stages:
            if stage.task_concurrency_limits:
                self._task_semaphores[stage.name] = {}
                for task_name, limit in stage.task_concurrency_limits.items():
                    self._task_semaphores[stage.name][task_name] = asyncio.Semaphore(limit)

    def get_worker_states(self) -> Dict[str, WorkerState]:
        """
        Get current state of all workers.

        Returns:
            Dictionary mapping worker name to [WorkerState][antflow.types.WorkerState]

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
            Dictionary mapping worker name to [WorkerMetrics][antflow.types.WorkerMetrics]

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
            [DashboardSnapshot][antflow.types.DashboardSnapshot] with worker states, metrics, and pipeline stats

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
            timestamp=time.time(),
        )

    async def feed(
        self, 
        items: Sequence[Any], 
        target_stage: Optional[str] = None,
        priority: int = 100
    ) -> None:
        """
        Feed items into a specific stage of the pipeline.

        Args:
            items: Sequence of items to process
            target_stage: Name of the stage to inject items into. 
                         If None, feeds into the first stage.
            priority: Priority level (lower = higher priority). Default 100.
        
        Raises:
            ValueError: If target_stage is provided but not found.
        """
        if target_stage is None:
            q = self._queues[0]
            stage_name = self.stages[0].name if self.stages else None
        else:
            try:
                # Find stage index by name
                stage_idx = next(i for i, s in enumerate(self.stages) if s.name == target_stage)
                q = self._queues[stage_idx]
                stage_name = target_stage
            except StopIteration:
                raise ValueError(f"Stage '{target_stage}' not found in pipeline")

        for item in items:
            payload = self._prepare_payload(item)
            # (priority, sequence, data)
            # We use _msg_counter to ensure stability (FIFO for same priority)
            seq = self._msg_counter
            self._msg_counter += 1
            await q.put((priority, seq, (payload, 1)))
            
            logger.debug(f"Enqueued item id={payload['id']} to stage={stage_name} prio={priority}")
            await self._emit_status(payload["id"], stage_name, "queued")

    async def feed_async(
        self, 
        items: AsyncIterable[Any], 
        target_stage: Optional[str] = None,
        priority: int = 100
    ) -> None:
        """
        Feed items from an async iterable into a specific stage.

        Args:
            items: Async iterable of items to process
            target_stage: Name of the stage to inject items into.
                         If None, feeds into the first stage.
            priority: Priority level (lower = higher priority). Default 100.

        Raises:
            ValueError: If target_stage is provided but not found.
        """
        if target_stage is None:
            q = self._queues[0]
            stage_name = self.stages[0].name if self.stages else None
        else:
            try:
                stage_idx = next(i for i, s in enumerate(self.stages) if s.name == target_stage)
                q = self._queues[stage_idx]
                stage_name = target_stage
            except StopIteration:
                raise ValueError(f"Stage '{target_stage}' not found in pipeline")

        async for item in items:
            payload = self._prepare_payload(item)
            seq = self._msg_counter
            self._msg_counter += 1
            await q.put((priority, seq, (payload, 1)))

            logger.debug(f"Enqueued item id={payload['id']} to stage={stage_name} prio={priority}")
            await self._emit_status(payload["id"], stage_name, "queued")

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
                "_sequence_id": self._sequence_counter,
            }
            for k, v in item.items():
                payload.setdefault(k, v)
        else:
            payload = {
                "id": self._sequence_counter,
                "value": item,
                "_sequence_id": self._sequence_counter,
            }

        self._sequence_counter += 1
        return payload

    async def start(self) -> None:
        """
        Start the pipeline workers in the background.
        
        This method initializes the worker pool and starts processing items immediately
        as they are available in the queues. Use `feed()` to add items.
        
        Raises:
            PipelineError: If pipeline is already running
        """
        if self._runner_task and not self._runner_task.done():
            raise PipelineError("Pipeline is already running")
            
        self._stop_event.clear()
        self._shutdown = False
        self._worker_tasks = []
        self._runner_task = asyncio.create_task(self._backend_runner())
    
    async def join(self) -> None:
        """
        Wait for all enqueued items to be processed and stop workers.
        
        This method:
        1. Waits for all queues to be empty (all items processed)
        2. Signals workers to stop
        3. Waits for the worker pool to shutdown
        """
        if not self._runner_task:
            return

        # Wait for all queues to automatically join (empty)
        # Note: If a worker crashes, the queue might not join properly without
        # careful error handling, but queue.join() waits for task_done() calls.
        logger.debug("Waiting for queues to drain...")
        for q in self._queues:
            await q.join()
            
        logger.debug("Queues drained, signaling stop...")
        self._stop_event.set()
        
        if self._runner_task:
            await self._runner_task
            self._runner_task = None
            
    async def _backend_runner(self) -> None:
        """Internal runner that manages the TaskGroup and workers."""
        try:
            async with TaskGroup() as tg:
                for stage_index, stage in enumerate(self.stages):
                    name_prefix = stage.name
                    input_q = self._queues[stage_index]
                    output_q = (
                        self._queues[stage_index + 1] if stage_index + 1 < len(self._queues) else None
                    )

                    for i in range(stage.workers):
                        worker_name = f"{name_prefix}-W{i}"
                        task = tg.create_task(
                            self._stage_worker(worker_name, stage_index, stage, input_q, output_q)
                        )
                        self._worker_tasks.append(task)
                        
                # Wait for stop signal
                # Workers themselves monitor stop_event, so we just wait for them to finish
                # which happens when stop_event is set AND queues are empty (per _stage_worker logic)
                # TaskGroup will wait for all tasks to complete upon exit.
                
        except Exception as e:
            logger.error(f"Pipeline backend runner failed: {e}")
            raise

    async def run(self, items: Sequence[Any]) -> List[PipelineResult]:
        """
        Run the pipeline end-to-end with the given items.
        
        This is a convenience wrapper around `start()`, `feed()`, and `join()`.

        Args:
            items: Items to process through the pipeline.

        Returns:
            List of [PipelineResult][antflow.types.PipelineResult] objects.
        """
        await self.start()
        await self.feed(items)
        await self.join()
        return self.results

    async def shutdown(self) -> None:
        """
        Shut down the pipeline gracefully or forcefully.
        
        If queues are not empty, this might leave items unprocessed depending on
        how workers react to stop_event.
        """
        if self._shutdown:
            return

        logger.debug("Shutting down pipeline")
        self._shutdown = True
        self._stop_event.set()

        if self._runner_task:
            # If we want to force cancel, we would cancel the runner task.
            # But graceful shutdown prefers letting them finish current item.
            # The workers check stop_event loop.
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                self._runner_task = None

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
        metadata: Dict[str, Any] | None = None,
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
                metadata=metadata or {},
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
        duration: Optional[float] = None,
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
                duration=duration,
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
                # Unpack priority item
                # (priority, sequence, (payload, attempt))
                prio_item = await asyncio.wait_for(input_q.get(), timeout=0.1)
                priority, seq_in, (payload, attempt) = prio_item
            except asyncio.TimeoutError:
                continue

            item_id = payload.get("id")
            start_time = time.time()

            self._worker_states[name].status = "busy"
            self._worker_states[name].current_item_id = item_id
            self._worker_states[name].processing_since = start_time

            try:
                logger.debug(f"[{name}] START stage={stage.name} id={item_id} attempt={attempt} prio={priority}")

                # SKIP Logic
                should_skip = False
                if stage.skip_if:
                    try:
                        should_skip = stage.skip_if(payload["value"])
                    except Exception as e:
                        logger.warning(f"[{name}] Error in skip_if predicate for id={item_id}: {e}")
                        should_skip = False
                
                if should_skip:
                    logger.info(f"[{name}] SKIP stage={stage.name} id={item_id}")
                    await self._emit_status(item_id, stage.name, "skipped", worker=name)
                    # Pass-through value
                    result_value = payload["value"]
                else:
                    await self._emit_status(item_id, stage.name, "in_progress", worker=name)

                    if stage.retry == "per_task":
                        result_value = await self._run_per_task(stage, payload["value"], name, item_id)
                    else:
                        result_value = await self._run_per_stage(
                            stage, payload["value"], name, item_id, payload, attempt, input_q, priority
                        )
                        if result_value is None:
                            continue

                payload["value"] = result_value
                
                # Emit completed if not skipped? Or is skipped enough?
                # "skipped" is the final status for this stage. 
                # But to trigger "queued" for next stage, we just proceed.
                if not should_skip:
                    await self._emit_status(item_id, stage.name, "completed", worker=name)

                if output_q is not None:
                    # Propagate priority, use new sequence number for stability in next queue
                    seq_out = self._msg_counter
                    self._msg_counter += 1
                    await output_q.put((priority, seq_out, (payload, 1)))

                    is_not_last_stage = stage_index + 1 < len(self.stages)
                    next_stage_name = (
                        self.stages[stage_index + 1].name if is_not_last_stage else None
                    )
                    if next_stage_name:
                        await self._emit_status(item_id, next_stage_name, "queued")
                else:
                    if self.collect_results:
                        # Extract known fields
                        res_id = payload["id"]
                        res_value = payload["value"]
                        seq_id = payload["_sequence_id"]
                        # Everything else goes to metadata
                        meta = {
                            k: v
                            for k, v in payload.items()
                            if k not in ("id", "value", "_sequence_id")
                        }

                        self._results.append(
                            PipelineResult(
                                id=res_id, value=res_value, sequence_id=seq_id, metadata=meta
                            )
                        )

                if stage.on_success:
                    try:
                        if asyncio.iscoroutinefunction(stage.on_success):
                            await stage.on_success(item_id, payload["value"], payload)
                        else:
                            stage.on_success(item_id, payload["value"], payload)
                    except Exception as e:
                        logger.error(f"[{name}] Error in on_success callback: {e}")

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
                    item_id, stage.name, "failed", metadata={"error": str(original_error)}
                )

                if stage.on_failure:
                    try:
                        if asyncio.iscoroutinefunction(stage.on_failure):
                            await stage.on_failure(item_id, original_error, {})
                        else:
                            stage.on_failure(item_id, original_error, {})
                    except Exception as e:
                        logger.error(f"[{name}] Error in on_failure callback: {e}")
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
            wrapped = self._wrap_with_tenacity(task, stage, worker_name, item_id, task_name)

            logger.debug(
                f"[{worker_name}] START task {idx + 1}/{len(stage.tasks)}={task_name} id={item_id}"
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
                    f"[{worker_name}] END task {idx + 1}/{len(stage.tasks)}={task_name} id={item_id}"
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
        priority: int,
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
            priority: Priority level

        Returns:
            Final value if successful, None if retried or failed
        """
        current = value

        try:
            for idx, task in enumerate(stage.tasks):
                task_name = task.__name__

                logger.debug(
                    f"[{worker_name}] START task {idx + 1}/{len(stage.tasks)}="
                    f"{task_name} id={item_id}"
                )

                if stage.unpack_args:
                    if isinstance(current, dict):
                        coro = task(**current)
                    elif isinstance(current, (list, tuple)):
                        coro = task(*current)
                    else:
                        coro = task(current)
                else:
                    coro = task(current)

                # Acquire semaphore if limit exists
                semaphore = self._task_semaphores.get(stage.name, {}).get(task_name)
                if semaphore:
                    async with semaphore:
                        current = await coro
                else:
                    current = await coro

                logger.debug(
                    f"[{worker_name}] END task {idx + 1}/{len(stage.tasks)}={task_name} id={item_id}"
                )

            return current

        except Exception as e:
            original_error = extract_exception(e)

            if attempt < stage.stage_attempts:
                logger.debug(
                    f"[{worker_name}] RETRY stage={stage.name} id={item_id} "
                    f"attempt={attempt} error={original_error}"
                )

                # Re-queue with same priority (or could boost it here)
                seq_retry = self._msg_counter
                self._msg_counter += 1
                await input_q.put((priority, seq_retry, (payload, attempt + 1)))

                await self._emit_status(
                    item_id,
                    stage.name,
                    "retrying",
                    metadata={"attempt": attempt + 1, "retry": True, "error": str(original_error)},
                )

                return None
            else:
                logger.error(
                    f"[{worker_name}] FAIL stage={stage.name} id={item_id} "
                    f"after {attempt} attempts error={original_error}"
                )

                self._items_failed += 1

                await self._emit_status(
                    item_id, stage.name, "failed", metadata={"error": str(original_error)}
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
            stop=stop_after_attempt(stage.task_attempts), wait=wait_fixed(stage.task_wait_seconds)
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
                attempt=current_attempt,
            )

            try:
                # Acquire semaphore if limit exists
                semaphore = self._task_semaphores.get(stage.name, {}).get(task_name)
                if semaphore:
                    async with semaphore:
                        result = await task(*args, **kwargs)
                else:
                    result = await task(*args, **kwargs)

                duration = time.time() - start_time

                await self._emit_task_event(
                    item_id=item_id,
                    stage=stage.name,
                    task_name=task_name,
                    worker=worker_name,
                    event_type="complete",
                    attempt=current_attempt,
                    duration=duration,
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
                        duration=duration,
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
                        duration=duration,
                    )

                raise

        return wrapped
