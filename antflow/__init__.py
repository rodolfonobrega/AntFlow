"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

from ._version import __version__
from .context import set_task_status
from .exceptions import (
    AntFlowError,
    ExecutorShutdownError,
    PipelineError,
    StageValidationError,
    TaskFailedError,
)
from .executor import AsyncExecutor, AsyncFuture, WaitStrategy
from .pipeline import Pipeline, PipelineBuilder, Stage
from .tracker import StatusEvent, StatusTracker
from .types import (
    DashboardProtocol,
    DashboardSnapshot,
    ErrorSummary,
    FailedItem,
    PipelineResult,
    PipelineStats,
    StatusType,
    TaskEvent,
    TaskEventType,
    TaskFunc,
    WorkerMetrics,
    WorkerState,
    WorkerStatus,
)

__all__ = [
    "__version__",
    "AsyncExecutor",
    "AsyncFuture",
    "AntFlowError",
    "DashboardProtocol",
    "DashboardSnapshot",
    "ErrorSummary",
    "ExecutorShutdownError",
    "FailedItem",
    "PipelineResult",
    "Pipeline",
    "PipelineBuilder",
    "PipelineError",
    "PipelineStats",
    "Stage",
    "StageValidationError",
    "StatusEvent",
    "StatusTracker",
    "StatusType",
    "TaskEvent",
    "TaskEventType",
    "TaskFailedError",
    "TaskFunc",
    "WaitStrategy",
    "WorkerMetrics",
    "WorkerState",
    "WorkerStatus",
    "set_task_status",
]
