"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

from ._version import __version__

# Auto-activate the fastest available event loop for this platform.
# uvloop on Linux/macOS, winloop on Windows — transparent to the user.
import sys as _sys
try:
    if _sys.platform in ("win32", "cygwin", "cli"):
        import winloop as _fast_loop
    else:
        import uvloop as _fast_loop
    _fast_loop.install()
    del _fast_loop
except ImportError:
    pass
del _sys
from .context import set_task_status
from .exceptions import (
    AntFlowError,
    ExecutorShutdownError,
    PipelineError,
    StageValidationError,
    TaskFailedError,
)
from .executor import AsyncExecutor, AsyncFuture, WaitStrategy
from .pipeline import Pipeline, PipelineBuilder, RendezvousChannel, Stage
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
    "RendezvousChannel",
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
