"""Tests for AsyncExecutor concurrency limits."""

import asyncio

import pytest

from antflow import AsyncExecutor


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

    async with AsyncExecutor(max_workers=10) as executor:
        futures = []
        for i in range(10):
            f = executor.submit(tracked_task, i, semaphore=semaphore)
            futures.append(f)

        await asyncio.gather(*[f.result() for f in futures])

    assert max_active <= 2
    assert max_active == 2


@pytest.mark.asyncio
async def test_workers_limit_concurrency():
    """Test that max_workers limits concurrent executions."""
    active_tasks = 0
    max_active = 0

    async def tracked_task(x):
        nonlocal active_tasks, max_active
        active_tasks += 1
        max_active = max(max_active, active_tasks)
        await asyncio.sleep(0.05)
        active_tasks -= 1
        return x

    async with AsyncExecutor(max_workers=3) as executor:
        results = await executor.map(tracked_task, range(10))

    assert len(results) == 10
    assert max_active <= 3
    assert max_active == 3
