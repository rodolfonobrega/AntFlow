"""Tests for AsyncExecutor concurrency limits."""

import asyncio
import time
import pytest
from antflow import AsyncExecutor


@pytest.mark.asyncio
async def test_map_max_concurrency():
    """Test that map respects max_concurrency."""
    # We'll use a counter to track concurrent executions
    active_tasks = 0
    max_active = 0

    async def tracked_task(x):
        nonlocal active_tasks, max_active
        active_tasks += 1
        max_active = max(max_active, active_tasks)
        await asyncio.sleep(0.1)
        active_tasks -= 1
        return x

    # Executor has 10 workers, but we limit map to 3
    async with AsyncExecutor(max_workers=10) as executor:
        results = []
        async for res in executor.map(tracked_task, range(10), max_concurrency=3):
            results.append(res)

    assert len(results) == 10
    assert max_active <= 3
    # It should have reached 3 at some point given 10 tasks and 10 workers
    assert max_active == 3


@pytest.mark.asyncio
async def test_submit_semaphore():
    """Test that submit respects shared semaphore."""
    active_tasks = 0
    max_active = 0
    semaphore = asyncio.Semaphore(2)

    async def tracked_task(x):
        nonlocal active_tasks, max_active
        active_tasks += 1
        max_active = max(max_active, active_tasks)
        await asyncio.sleep(0.1)
        active_tasks -= 1
        return x

    # Executor has 10 workers, but semaphore limits to 2
    async with AsyncExecutor(max_workers=10) as executor:
        futures = []
        for i in range(10):
            f = executor.submit(tracked_task, i, semaphore=semaphore)
            futures.append(f)

        await asyncio.gather(*[f.result() for f in futures])

    assert max_active <= 2
    assert max_active == 2
