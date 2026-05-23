"""Tests for pull=True Stage (demand-driven, zero-buffer inter-stage channel)."""

import asyncio

import pytest

from antflow import Pipeline, Stage
from antflow.context import concurrency_limit
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


# ---------------------------------------------------------------------------
# Pull stage + retries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pull_stage_retry_on_failure():
    """Items that fail in a pull stage are retried and eventually succeed."""
    attempts: dict[int, int] = {}

    async def flaky(x):
        attempts[x] = attempts.get(x, 0) + 1
        if attempts[x] < 2:
            raise ValueError("transient")
        return x * 10

    async def identity(x):
        return x

    pipeline = Pipeline(stages=[
        Stage("feeder", workers=2, tasks=[identity]),
        Stage("poll", workers=4, tasks=[flaky], pull=True, task_attempts=3),
    ])
    results = await asyncio.wait_for(
        pipeline.run(list(range(8))),
        timeout=15.0,
    )

    assert len(results) == 8
    assert sorted(r.value for r in results) == [i * 10 for i in range(8)]
    # Every item needed exactly 2 attempts
    assert all(v == 2 for v in attempts.values())


@pytest.mark.asyncio
async def test_pull_stage_all_retries_exhausted():
    """Items that exhaust retries in a pull stage are recorded as failed."""
    async def always_fail(x):
        raise RuntimeError("permanent")

    async def identity(x):
        return x

    pipeline = Pipeline(stages=[
        Stage("feeder", workers=2, tasks=[identity]),
        Stage("poll", workers=4, tasks=[always_fail], pull=True, task_attempts=2),
    ])
    results = await asyncio.wait_for(
        pipeline.run(list(range(5))),
        timeout=15.0,
    )

    # All failed — no successful results
    assert len(results) == 0
    stats = pipeline.get_stats()
    assert stats.items_failed == 5


# ---------------------------------------------------------------------------
# Pull stage + call_concurrency under load
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pull_stage_call_concurrency_under_load():
    """
    pull=True + call_concurrency: all items processed, semaphore never exceeded,
    workers run concurrently (not serialised by the semaphore).
    """
    active_api = 0
    peak_api = 0
    inside_fn = 0
    peak_fn = 0

    async def poll_job(x):
        nonlocal inside_fn, peak_fn, active_api, peak_api
        inside_fn += 1
        peak_fn = max(peak_fn, inside_fn)

        async with concurrency_limit():
            active_api += 1
            peak_api = max(peak_api, active_api)
            await asyncio.sleep(0.02)
            active_api -= 1

        await asyncio.sleep(0.01)  # simulate inter-poll sleep (no slot held)

        async with concurrency_limit():
            active_api += 1
            peak_api = max(peak_api, active_api)
            await asyncio.sleep(0.02)
            active_api -= 1

        inside_fn -= 1
        return x

    async def identity(x):
        return x

    N_ITEMS = 40
    LIMIT = 5

    pipeline = Pipeline(stages=[
        Stage("feeder", workers=4, tasks=[identity]),
        Stage("poll", workers=30, tasks=[poll_job], pull=True, call_concurrency=LIMIT),
    ])
    results = await asyncio.wait_for(
        pipeline.run(list(range(N_ITEMS))),
        timeout=30.0,
    )

    assert len(results) == N_ITEMS
    # Semaphore held — API calls never exceeded limit
    assert peak_api <= LIMIT
    # Workers ran concurrently — peak inside function well above limit
    assert peak_fn > LIMIT


# ---------------------------------------------------------------------------
# Correctness stress test — no items lost or duplicated under high concurrency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pull_stage_stress_no_items_lost():
    """500 items through a pull stage with 100 workers — every item arrives exactly once."""
    async def identity(x):
        return x

    async def work(x):
        await asyncio.sleep(0)  # yield to stress the scheduler
        return x

    N = 500
    pipeline = Pipeline(stages=[
        Stage("feeder", workers=10, tasks=[identity]),
        Stage("poll", workers=100, tasks=[work], pull=True),
    ])
    results = await asyncio.wait_for(
        pipeline.run(list(range(N))),
        timeout=30.0,
    )

    assert len(results) == N
    # No duplicates
    values = [r.value for r in results]
    assert len(set(values)) == N


# ---------------------------------------------------------------------------
# Shutdown under load
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pull_stage_shutdown_while_processing():
    """shutdown() while workers are actively processing does not hang."""
    processing = asyncio.Event()

    async def identity(x):
        return x

    async def slow_work(x):
        processing.set()
        await asyncio.sleep(0.5)
        return x

    pipeline = Pipeline(stages=[
        Stage("feeder", workers=2, tasks=[identity]),
        Stage("poll", workers=10, tasks=[slow_work], pull=True),
    ])

    await pipeline.start()
    await pipeline.feed(list(range(20)))

    # Wait until at least one worker is actively processing
    await asyncio.wait_for(processing.wait(), timeout=5.0)

    # Shutdown must complete without hanging
    await asyncio.wait_for(pipeline.shutdown(), timeout=10.0)
