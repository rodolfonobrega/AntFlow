"""Tests targeting specific coverage gaps found via coverage report."""

from __future__ import annotations

import asyncio

import pytest

from antflow import Pipeline, Stage
from antflow.context import set_task_status

# ---------------------------------------------------------------------------
# feed(target_stage=...) — inject items directly into a named stage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feed_target_stage_valid():
    """Items fed into a named stage bypass earlier stages."""
    processed_by_b = []

    async def stage_a(x):
        return x * 10  # should never run

    async def stage_b(x):
        processed_by_b.append(x)
        return x

    pipeline = Pipeline(stages=[
        Stage("A", workers=2, tasks=[stage_a]),
        Stage("B", workers=2, tasks=[stage_b]),
    ])

    await pipeline.start()
    await pipeline.feed([1, 2, 3], target_stage="B")
    await pipeline.join()

    # Items went straight to B — stage_a never touched them
    assert sorted(processed_by_b) == [1, 2, 3]


@pytest.mark.asyncio
async def test_feed_target_stage_invalid_raises():
    """Feeding into a non-existent stage raises ValueError."""
    async def noop(x):
        return x

    pipeline = Pipeline(stages=[Stage("A", workers=1, tasks=[noop])])
    await pipeline.start()

    with pytest.raises(ValueError, match="not found"):
        await pipeline.feed([1], target_stage="nonexistent")

    await pipeline.shutdown()


@pytest.mark.asyncio
async def test_feed_async_target_stage_valid():
    """feed_async() with a named stage injects into that stage directly."""
    processed_by_b = []

    async def stage_a(x):
        return x * 10  # should never run

    async def stage_b(x):
        processed_by_b.append(x)
        return x

    async def async_items():
        for i in [1, 2, 3]:
            yield i

    pipeline = Pipeline(stages=[
        Stage("A", workers=2, tasks=[stage_a]),
        Stage("B", workers=2, tasks=[stage_b]),
    ])

    await pipeline.start()
    await pipeline.feed_async(async_items(), target_stage="B")
    await pipeline.join()

    assert sorted(processed_by_b) == [1, 2, 3]


@pytest.mark.asyncio
async def test_feed_async_target_stage_invalid_raises():
    """feed_async() with a non-existent stage raises ValueError."""
    async def noop(x):
        return x

    async def async_items():
        yield 1

    pipeline = Pipeline(stages=[Stage("A", workers=1, tasks=[noop])])
    await pipeline.start()

    with pytest.raises(ValueError, match="not found"):
        await pipeline.feed_async(async_items(), target_stage="nonexistent")

    await pipeline.shutdown()


# ---------------------------------------------------------------------------
# unpack_args=True — dict, list/tuple, and plain value branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unpack_args_dict():
    """unpack_args=True with dict input unpacks as kwargs."""
    async def add(a, b):
        return a + b

    pipeline = Pipeline(stages=[
        Stage("S", workers=2, tasks=[add], unpack_args=True)
    ])
    results = await pipeline.run([{"a": 1, "b": 2}, {"a": 10, "b": 20}])

    assert sorted(r.value for r in results) == [3, 30]


@pytest.mark.asyncio
async def test_unpack_args_list():
    """unpack_args=True with list input unpacks as positional args."""
    async def add(a, b):
        return a + b

    pipeline = Pipeline(stages=[
        Stage("S", workers=2, tasks=[add], unpack_args=True)
    ])
    results = await pipeline.run([[1, 2], [10, 20]])

    assert sorted(r.value for r in results) == [3, 30]


@pytest.mark.asyncio
async def test_unpack_args_tuple():
    """unpack_args=True with tuple input unpacks as positional args."""
    async def multiply(a, b):
        return a * b

    pipeline = Pipeline(stages=[
        Stage("S", workers=2, tasks=[multiply], unpack_args=True)
    ])
    results = await pipeline.run([(3, 4), (5, 6)])

    assert sorted(r.value for r in results) == [12, 30]


# ---------------------------------------------------------------------------
# set_task_status() — min_interval rate limiting branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_task_status_outside_pipeline_returns_false():
    """set_task_status() returns False when called outside a pipeline worker."""
    result = set_task_status("hello")
    assert result is False


@pytest.mark.asyncio
async def test_set_task_status_updates_inside_pipeline():
    """set_task_status() returns True and updates status inside a worker."""
    statuses = []

    async def task(x):
        ok = set_task_status(f"processing {x}")
        statuses.append(ok)
        return x

    await Pipeline(stages=[Stage("S", workers=2, tasks=[task])]).run([1, 2, 3])

    assert all(s is True for s in statuses)


@pytest.mark.asyncio
async def test_set_task_status_min_interval_rate_limits():
    """
    When min_interval > 0, rapid successive calls are rate-limited.
    The first call returns True; a second call immediately after returns False.
    """
    results = []

    async def task(x):
        # Two back-to-back calls with a long min_interval
        r1 = set_task_status("first", min_interval=10.0)
        r2 = set_task_status("second", min_interval=10.0)  # should be suppressed
        results.append((r1, r2))
        return x

    await Pipeline(stages=[Stage("S", workers=1, tasks=[task])]).run([1])

    r1, r2 = results[0]
    assert r1 is True   # first call always goes through
    assert r2 is False  # second call within min_interval is suppressed


@pytest.mark.asyncio
async def test_set_task_status_min_interval_passes_after_wait():
    """A call after the min_interval has elapsed returns True."""
    results = []

    async def task(x):
        r1 = set_task_status("first", min_interval=0.05)
        await asyncio.sleep(0.1)  # wait longer than min_interval
        r2 = set_task_status("second", min_interval=0.05)
        results.append((r1, r2))
        return x

    await Pipeline(stages=[Stage("S", workers=1, tasks=[task])]).run([1])

    r1, r2 = results[0]
    assert r1 is True
    assert r2 is True  # enough time passed


# ---------------------------------------------------------------------------
# stream() with progress=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_with_progress():
    """stream(progress=True) completes without error and yields all items."""
    async def noop(x):
        return x

    pipeline = Pipeline(stages=[Stage("S", workers=2, tasks=[noop])])

    collected = []
    async for result in pipeline.stream(list(range(5)), progress=True):
        collected.append(result.value)

    assert sorted(collected) == [0, 1, 2, 3, 4]
