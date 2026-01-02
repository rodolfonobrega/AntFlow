"""Tests for Pipeline task concurrency limits."""

import asyncio

import pytest

from antflow import Pipeline, Stage


@pytest.mark.asyncio
async def test_pipeline_task_concurrency():
    """Test that pipeline respects task_concurrency_limits."""
    active_tasks = 0
    max_active = 0

    async def limited_task(x):
        nonlocal active_tasks, max_active
        active_tasks += 1
        max_active = max(max_active, active_tasks)
        await asyncio.sleep(0.1)
        active_tasks -= 1
        return x

    async def fast_task(x):
        return x

    # Stage has 10 workers, but limited_task is capped at 2
    stage = Stage(
        name="TestStage",
        workers=10,
        tasks=[limited_task, fast_task],
        task_concurrency_limits={"limited_task": 2},
    )

    pipeline = Pipeline(stages=[stage])

    # Run 10 items
    items = list(range(10))
    results = await pipeline.run(items)

    assert len(results) == 10
    assert max_active == 2
    # fast_task should have run without limits (implied by completion time if we measured it,
    # but correctness is main check here)


@pytest.mark.asyncio
async def test_pipeline_task_concurrency_per_stage_retry():
    """Test concurrency limits with retry='per_stage'."""
    active_tasks = 0
    max_active = 0

    async def limited_task(x):
        nonlocal active_tasks, max_active
        active_tasks += 1
        max_active = max(max_active, active_tasks)
        await asyncio.sleep(0.1)
        active_tasks -= 1
        return x

    stage = Stage(
        name="TestStage",
        workers=10,
        tasks=[limited_task],
        retry="per_stage",
        task_concurrency_limits={"limited_task": 2},
    )

    pipeline = Pipeline(stages=[stage])
    results = await pipeline.run(list(range(10)))

    assert len(results) == 10
    assert max_active == 2
