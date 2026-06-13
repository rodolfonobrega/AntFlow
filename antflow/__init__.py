"""
AntFlow: Async execution library with concurrent.futures-style API and advanced pipelines.
"""

import asyncio
import sys
from importlib import import_module

from ._version import __version__
from .context import call_rate_has_capacity, concurrency_limit, rate_limit, set_task_status
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


def install_fast_loop() -> None:
    """
    Install the fastest available event loop policy for the current platform.
    Uses winloop on Windows, and uvloop on Linux/macOS.
    """
    try:
        fast_loop = import_module(
            "winloop" if sys.platform in ("win32", "cygwin", "cli") else "uvloop"
        )
        asyncio.set_event_loop_policy(fast_loop.EventLoopPolicy())
    except Exception:
        pass


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
