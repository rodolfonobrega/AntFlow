"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

from ._version import __version__
from .dashboard import PipelineDashboard
from .exceptions import (
    AntFlowError,
    ExecutorShutdownError,
    PipelineError,
    StageValidationError,
    TaskFailedError,
)
from .executor import AsyncExecutor, AsyncFuture, WaitStrategy
from .pipeline import Pipeline, Stage
from .tracker import StatusEvent, StatusTracker
from .types import (
    DashboardSnapshot,
    OrderedResult,
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
    "DashboardSnapshot",
    "ExecutorShutdownError",
    "OrderedResult",
    "Pipeline",
    "PipelineDashboard",
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
]
