"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

# Auto-activate the fastest available event loop for this platform.
# uvloop on Linux/macOS, winloop on Windows — transparent to the user.
import sys as _sys

from ._version import __version__

try:
    # Don't override the policy if a loop is already running (e.g. Jupyter,
    # IPython autoawait, or an embedding app) — install() wouldn't affect the
    # running loop and switching policy underneath it is surprising.
    import asyncio as _asyncio
    try:
        _asyncio.get_running_loop()
        _loop_running = True
    except RuntimeError:
        _loop_running = False
    if not _loop_running:
        if _sys.platform in ("win32", "cygwin", "cli"):
            import winloop as _fast_loop
        else:
            import uvloop as _fast_loop
        _fast_loop.install()
        del _fast_loop
    del _asyncio, _loop_running
except Exception:
    # Never let an optional speedup break `import antflow` (missing wheel,
    # unsupported arch, install() failure, etc.).
    pass
del _sys
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
]
