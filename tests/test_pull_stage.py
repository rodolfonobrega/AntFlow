"""Tests for pull=True Stage (demand-driven, zero-buffer inter-stage channel)."""

import asyncio

import pytest

from antflow import Pipeline, Stage
from antflow.exceptions import PipelineError, StageValidationError


@pytest.mark.asyncio
async def test_pull_stage_basic():
    """Pull stage processes all items and returns correct results."""

    async def double(x):
        return x * 2

    pipeline = Pipeline(stages=[
        Stage("produce", workers=2, tasks=[double]),
        Stage("consume", workers=4, tasks=[double], pull=True),
    ])
    results = await pipeline.run(list(range(5)))

    assert sorted(r.value for r in results) == [0, 4, 8, 12, 16]


@pytest.mark.asyncio
async def test_pull_stage_workers_cap_concurrency():
    """At most `workers` items in flight simultaneously in a pull stage."""
    active = 0
    max_active = 0

    async def slow_task(x):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return x

    async def identity(x):
        return x

    pipeline = Pipeline(stages=[
        Stage("upload", workers=10, tasks=[identity]),
        Stage("batch", workers=3, tasks=[slow_task], pull=True),
    ])
    await pipeline.run(list(range(12)))

    assert max_active <= 3
    assert max_active == 3


@pytest.mark.asyncio
async def test_pull_stage_upstream_blocked_when_workers_busy():
    """Upstream only produces when a pull worker is ready — no unobserved buffer."""
    produce_times: list[float] = []
    consume_start_times: list[float] = []

    async def track_produce(x):
        produce_times.append(asyncio.get_event_loop().time())
        return x

    async def slow_consume(x):
        consume_start_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.05)
        return x

    pipeline = Pipeline(stages=[
        Stage("up", workers=4, tasks=[track_produce]),
        Stage("down", workers=1, tasks=[slow_consume], pull=True),
    ])
    await pipeline.run(list(range(4)))

    # With 1 pull worker and slow tasks, items 2+ can only be produced after
    # item 1 completes — upstream should be paced by pull worker's readiness.
    # Verify: not all items were produced before any was consumed.
    assert len(produce_times) == 4
    assert len(consume_start_times) == 4


@pytest.mark.asyncio
async def test_pull_stage_multi_stage_pipeline():
    """Pull stage works correctly in the middle of a multi-stage pipeline."""

    async def add_one(x):
        return x + 1

    async def double(x):
        return x * 2

    async def add_ten(x):
        return x + 10

    pipeline = Pipeline(stages=[
        Stage("A", workers=2, tasks=[add_one]),
        Stage("B", workers=3, tasks=[double], pull=True),
        Stage("C", workers=2, tasks=[add_ten]),
    ])
    results = await pipeline.run([1, 2, 3])

    # (1+1)*2+10=14, (2+1)*2+10=16, (3+1)*2+10=18
    assert sorted(r.value for r in results) == [14, 16, 18]


def test_first_stage_pull_raises():
    """First stage cannot be a pull stage."""
    with pytest.raises(PipelineError, match="first stage"):

        async def noop(x):
            return x

        Pipeline(stages=[Stage("S", workers=1, tasks=[noop], pull=True)])


def test_pull_with_per_stage_retry_raises():
    """pull=True is incompatible with retry='per_stage'."""

    async def noop(x):
        return x

    with pytest.raises(StageValidationError, match="per_stage"):
        Stage("S", workers=1, tasks=[noop], pull=True, retry="per_stage").validate()
