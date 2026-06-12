"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

from ._version import __version__

# Fast event loop policy helper
def install_fast_loop() -> None:
    """
    Install the fastest available event loop policy for the current platform.
    Uses winloop on Windows, and uvloop on Linux/macOS.
    """
    import sys
    import asyncio
    from importlib import import_module
    try:
        fast_loop = import_module(
            "winloop" if sys.platform in ("win32", "cygwin", "cli") else "uvloop"
        )
        asyncio.set_event_loop_policy(fast_loop.EventLoopPolicy())
    except Exception:
        pass

from .context import call_rate_has_capacity, concurrency_limit, rate_limit, set_task_status  # noqa: E402, I001
from .exceptions import (  # noqa: E402
    AntFlowError,
    ExecutorShutdownError,
    PipelineError,
    StageValidationError,
    TaskFailedError,
)
from .executor import AsyncExecutor, AsyncFuture, WaitStrategy  # noqa: E402
from .pipeline import Pipeline, PipelineBuilder, Stage  # noqa: E402
from .tracker import StatusEvent, StatusTracker  # noqa: E402
from .types import (  # noqa: E402
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
    "call_rate_has_capacity",
    "concurrency_limit",
    "rate_limit",
    "set_task_status",
    "install_fast_loop",
]
