from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, AsyncIterator, Optional

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter

    from .types import WorkerState

# Context variable to store the current worker's state object
worker_state_var: ContextVar[Optional[WorkerState]] = ContextVar("worker_state", default=None)

# Context variable for the stage-level call_concurrency semaphore
_call_semaphore_var: ContextVar[Optional[asyncio.Semaphore]] = ContextVar(
    "call_semaphore", default=None
)

# Context variable for the stage-level call_rate limiter
_call_limiter_var: ContextVar[Optional[AsyncLimiter]] = ContextVar(
    "call_limiter", default=None
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
async def concurrency_limit() -> AsyncIterator[None]:
    """
    Acquire the stage's ``call_concurrency`` semaphore.

    Use inside a task function to limit how many workers make a specific
    call simultaneously, without blocking the entire task invocation.

    Requires ``call_concurrency=N`` on the Stage.

    Example::

        from antflow import concurrency_limit

        async def poll_until_done(job_id):
            while True:
                async with concurrency_limit():
                    status = await openai_check(job_id)
                if status == "done":
                    return result
                await asyncio.sleep(10)

    Raises:
        RuntimeError: If the stage has no ``call_concurrency`` configured.
    """
    sem = _call_semaphore_var.get()
    if sem is None:
        raise RuntimeError(
            "concurrency_limit() called but no call_concurrency is configured on this stage. "
            "Set call_concurrency=N on the Stage to use concurrency_limit()."
        )
    async with sem:
        yield


def call_rate_has_capacity(amount: float = 1) -> bool:
    """
    Check whether the stage's rate limiter has budget available without acquiring it.

    Returns ``True`` if ``amount`` tokens are currently available in the leaky
    bucket, ``False`` if the budget is exhausted.  When no ``call_rate`` is
    configured on the stage, always returns ``True`` (no limit → always free).

    Useful for adaptive patterns — e.g. skip an expensive call and use a
    cheaper fallback when the rate budget is already empty::

        from antflow import call_rate_has_capacity, rate_limit

        async def adaptive_poll(job_id):
            if call_rate_has_capacity():
                async with rate_limit():
                    return await api_poll(job_id)
            return None  # defer until next iteration

    Args:
        amount: Token cost to check (default 1).
    """
    limiter = _call_limiter_var.get()
    if limiter is None:
        return True
    return limiter.has_capacity(amount)


@asynccontextmanager
async def rate_limit() -> AsyncIterator[None]:
    """
    Acquire the stage's ``call_rate`` leaky-bucket limiter.

    Blocks until the configured throughput budget is available, then enters
    the body.  Use this to respect time-based API rate limits (e.g. 100 RPM)
    without dropping requests.

    Requires ``call_rate=N`` (and optionally ``call_rate_period=T``) on the
    Stage.

    Example::

        from antflow import rate_limit

        async def call_openai(item):
            async with rate_limit():          # honours ≤ 100 calls / 60 s
                return await openai_client.complete(item)

    Raises:
        RuntimeError: If the stage has no ``call_rate`` configured.
    """
    limiter = _call_limiter_var.get()
    if limiter is None:
        raise RuntimeError(
            "rate_limit() called but no call_rate is configured on this stage. "
            "Set call_rate=N on the Stage to use rate_limit()."
        )
    async with limiter:
        yield
