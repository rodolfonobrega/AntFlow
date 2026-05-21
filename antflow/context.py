from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, AsyncIterator, Optional

if TYPE_CHECKING:
    from .types import WorkerState

# Context variable to store the current worker's state object
worker_state_var: ContextVar[Optional[WorkerState]] = ContextVar("worker_state", default=None)

# Context variable for the stage-level call_concurrency semaphore
_call_semaphore_var: ContextVar[Optional[asyncio.Semaphore]] = ContextVar(
    "call_semaphore", default=None
)

# Track last update time per worker (for rate limiting)
_last_update_time: ContextVar[float] = ContextVar("last_update_time", default=0.0)


def set_task_status(status: str, min_interval: float = 0.0) -> bool:
    """
    Update the status message for the current task.
    This change will be reflected in the dashboard.

    Args:
        status: The message to display as the current task status.
        min_interval: Minimum seconds between updates (default: 0.0 = no limit).
                     Use this to avoid excessive updates in tight loops.
                     Example: min_interval=0.5 means max 2 updates per second.

    Returns:
        True if status was updated, False if rate-limited.

    Examples:
        ```python
        # No rate limiting (default)
        set_task_status("Processing...")

        # Rate limit to max 2 updates per second
        set_task_status("Processing item 1...", min_interval=0.5)
        set_task_status("Processing item 2...", min_interval=0.5)  # May be skipped if too fast

        # Common pattern: update only every N iterations
        for i in range(1000):
            if i % 10 == 0:  # Update every 10 items
                set_task_status(f"Processing {i}/1000...")
        ```
    """
    state = worker_state_var.get()
    if not state:
        return False

    # Check rate limiting
    if min_interval > 0:
        now = time.time()
        last_update = _last_update_time.get()

        if now - last_update < min_interval:
            return False  # Rate limited, skip this update

        _last_update_time.set(now)

    # Update the status
    state.current_task = status
    return True


def get_worker_state() -> Optional[WorkerState]:
    """Get the current worker's state object."""
    return worker_state_var.get()


@asynccontextmanager
async def rate_limit() -> AsyncIterator[None]:
    """
    Acquire the stage's call_concurrency semaphore.

    Use inside a task function to limit how many workers make a specific
    call simultaneously, without blocking the entire task invocation.

    Requires ``call_concurrency=N`` on the Stage.

    Example::

        from antflow.context import rate_limit

        async def poll_until_done(job_id):
            while True:
                async with rate_limit():
                    status = await openai_check(job_id)
                if status == "done":
                    return result
                await asyncio.sleep(10)

    Raises:
        RuntimeError: If called outside a pipeline worker or if the stage
            has no ``call_concurrency`` configured.
    """
    sem = _call_semaphore_var.get()
    if sem is None:
        raise RuntimeError(
            "rate_limit() called but no call_concurrency is configured on this stage. "
            "Set call_concurrency=N on the Stage to use rate_limit()."
        )
    async with sem:
        yield
