from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    runtime_checkable,
)

if TYPE_CHECKING:
    from .pipeline import Pipeline

TaskFunc = Callable[[Any], Awaitable[Any]]
StatusType = Literal["queued", "in_progress", "completed", "failed", "retrying", "skipped"]
WorkerStatus = Literal["idle", "busy"]
TaskEventType = Literal["start", "complete", "retry", "fail"]





@dataclass
class PipelineResult:
    """
    Result of a pipeline execution for a single item.

    Attributes:
        id: Unique identifier of the item
        value: The final processed value
        sequence_id: Internal sequence number for ordering
        metadata: Additional metadata from the input item
        error: Exception if processing failed (usually None for successful results)
    """
    id: Any
    value: Any
    sequence_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None

    @property
    def is_success(self) -> bool:
        """Check if processing was successful."""
        return self.error is None


@dataclass
class StageStats:
    """
    Statistics for a single stage.

    Attributes:
        stage_name: Name of the stage
        pending_items: Number of items in the queue
        in_progress_items: Number of items currently being processed (busy workers)
        completed_items: Total items successfully processed by this stage
        failed_items: Total items failed in this stage
    """
    stage_name: str
    pending_items: int
    in_progress_items: int
    completed_items: int
    failed_items: int


@dataclass
class PipelineStats:
    """
    Aggregate statistics for the pipeline.

    Attributes:
        items_processed: Total number of items successfully processed (final output)
        items_failed: Total number of items that failed
        items_in_flight: Number of items currently being processed anywhere
        queue_sizes: Dictionary mapping stage names to current queue sizes
        stage_stats: Detailed statistics per stage
    """
    items_processed: int
    items_failed: int
    items_in_flight: int
    queue_sizes: Dict[str, int]
    stage_stats: Dict[str, StageStats] = field(default_factory=dict)


@dataclass
class WorkerState:
    """
    Current state of a worker.

    Attributes:
        worker_name: Unique name of the worker (e.g., 'Fetch-W0')
        stage: Name of the stage this worker belongs to
        status: Current status ('idle' or 'busy')
        current_item_id: ID of the item currently being processed (if busy)
        processing_since: Timestamp when current processing started
    """
    worker_name: str
    stage: str
    status: WorkerStatus
    current_item_id: Optional[Any] = None
    processing_since: Optional[float] = None


@dataclass
class WorkerMetrics:
    """
    Performance metrics for a single worker.

    Attributes:
        worker_name: Unique name of the worker
        stage: Name of the stage
        items_processed: Count of successfully processed items
        items_failed: Count of failed items
        total_processing_time: Cumulative processing time in seconds
        last_active: Timestamp of last activity
    """
    worker_name: str
    stage: str
    items_processed: int = 0
    items_failed: int = 0
    total_processing_time: float = 0.0
    last_active: Optional[float] = None

    @property
    def avg_processing_time(self) -> float:
        """Calculate average processing time per item."""
        if self.items_processed == 0:
            return 0.0
        return self.total_processing_time / self.items_processed


@dataclass
class TaskEvent:
    """
    Event emitted for task-level operations within a stage.

    Provides granular visibility into individual task execution,
    including retries and failures at the task level.

    Attributes:
        item_id: Item being processed
        stage: Stage name
        task_name: Name of the specific task function
        worker: Worker name processing the task
        event_type: Type of event ([TaskEventType][antflow.types.TaskEventType])
        attempt: Current attempt number (1-indexed)
        timestamp: Unix timestamp when event occurred
        error: Exception if task failed or is retrying (None otherwise)
        duration: Time taken to execute task in seconds (None for start events)
    """
    item_id: Any
    stage: str
    task_name: str
    worker: str
    event_type: TaskEventType
    attempt: int
    timestamp: float
    error: Optional[Exception] = None
    duration: Optional[float] = None


@dataclass
class DashboardSnapshot:
    """
    Snapshot of the entire pipeline state for monitoring.

    Attributes:
        worker_states: Dictionary of all [WorkerState][antflow.types.WorkerState]
        worker_metrics: Dictionary of all [WorkerMetrics][antflow.types.WorkerMetrics]
        pipeline_stats: Aggregate [PipelineStats][antflow.types.PipelineStats]
        timestamp: Timestamp when snapshot was taken
    """
    worker_states: Dict[str, WorkerState]
    worker_metrics: Dict[str, WorkerMetrics]
    pipeline_stats: PipelineStats
    timestamp: float


@dataclass
class StatusEvent:
    """
    Represents a status change event for an item in the pipeline.

    Attributes:
        item_id: Unique identifier for the item
        stage: Name of the stage (None if not stage-specific)
        status: Current status of the item
        worker: Name of the worker processing the item (if applicable)
        timestamp: Unix timestamp when the event occurred
        metadata: Additional metadata about the event
    """
    item_id: Any
    stage: str | None
    status: StatusType
    worker: str | None
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def worker_id(self) -> int | None:
        """
        Extract worker ID from worker name.

        Examples:
            "ProcessBatch-W5" -> 5
            "Fetch-W0" -> 0
            None -> None

        Returns:
            Worker ID (0-indexed) or None if not available
        """
        if self.worker:
            try:
                return int(self.worker.split('-W')[-1])
            except (ValueError, IndexError):
                return None
        return None


@dataclass
class FailedItem:
    """
    Details of a single failed item.

    Attributes:
        item_id: Unique identifier of the failed item
        error: Error message string
        error_type: Type name of the exception
        stage: Stage where failure occurred
        attempts: Number of attempts made before failure
        timestamp: Unix timestamp when failure occurred
    """

    item_id: Any
    error: str
    error_type: str
    stage: str
    attempts: int
    timestamp: float


@dataclass
class ErrorSummary:
    """
    Aggregated error information from pipeline execution.

    Attributes:
        total_failed: Total count of failed items
        errors_by_type: Count of errors grouped by exception type
        errors_by_stage: Count of errors grouped by stage name
        failed_items: List of individual failed item details
    """

    total_failed: int
    errors_by_type: Dict[str, int]
    errors_by_stage: Dict[str, int]
    failed_items: List[FailedItem]

    def __str__(self) -> str:
        if self.total_failed == 0:
            return "No errors occurred"

        lines = [
            f"ErrorSummary: {self.total_failed} failed items",
            "",
            "By type:",
        ]
        for error_type, count in sorted(
            self.errors_by_type.items(), key=lambda x: -x[1]
        ):
            lines.append(f"  {error_type}: {count}")

        lines.append("")
        lines.append("By stage:")
        for stage, count in sorted(self.errors_by_stage.items(), key=lambda x: -x[1]):
            lines.append(f"  {stage}: {count}")

        return "\n".join(lines)


@runtime_checkable
class DashboardProtocol(Protocol):
    """
    Protocol for custom dashboard implementations.

    Implement this protocol to create custom dashboards that integrate
    with Pipeline.run()'s dashboard parameter.

    Example:
        ```python
        class MyDashboard:
            def on_start(self, pipeline, total_items):
                print(f"Starting {total_items} items")

            def on_update(self, snapshot):
                print(f"Progress: {snapshot.pipeline_stats.items_processed}")

            def on_finish(self, results, summary):
                print(f"Done! {len(results)} results, {summary.total_failed} failed")

        results = await pipeline.run(items, custom_dashboard=MyDashboard())
        ```
    """

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """Called when pipeline execution starts."""
        ...

    def on_update(self, snapshot: DashboardSnapshot) -> None:
        """Called periodically with current pipeline state."""
        ...

    def on_finish(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Called when pipeline execution completes."""
        ...
