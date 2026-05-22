"""
Tests for concurrency_limit() (semaphore) and rate_limit() (leaky bucket).
"""
from __future__ import annotations

import asyncio
import time

import pytest

from antflow import Pipeline, Stage, call_rate_has_capacity, concurrency_limit, rate_limit

# ---------------------------------------------------------------------------
# concurrency_limit() — semaphore behaviour (renamed from rate_limit)
# ---------------------------------------------------------------------------

async def test_concurrency_limit_enforces_cap():
    """At most N workers enter the body simultaneously."""
    active = 0
    max_active = 0

    async def task(item):
        nonlocal active, max_active
        async with concurrency_limit():
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
        return item

    pipeline = Pipeline(
        stages=[Stage("s", workers=10, tasks=[task], call_concurrency=3)],
        collect_results=True,
    )
    await pipeline.run(list(range(10)))
    assert max_active <= 3


async def test_concurrency_limit_raises_without_config():
    """concurrency_limit() outside a stage with call_concurrency raises."""
    with pytest.raises(RuntimeError, match="call_concurrency"):
        async with concurrency_limit():
            pass


# ---------------------------------------------------------------------------
# rate_limit() — leaky bucket behaviour
# ---------------------------------------------------------------------------

async def test_rate_limit_raises_without_config():
    """rate_limit() outside a stage with call_rate raises."""
    with pytest.raises(RuntimeError, match="call_rate"):
        async with rate_limit():
            pass


async def test_rate_limit_throttles_throughput():
    """
    Stage with call_rate=5, call_rate_period=1 should allow at most ~5 acquisitions
    in one second even with many concurrent workers.
    """
    timestamps: list[float] = []

    async def task(item):
        async with rate_limit():
            timestamps.append(time.monotonic())
        return item

    pipeline = Pipeline(
        stages=[Stage("s", workers=10, tasks=[task], call_rate=5, call_rate_period=1.0)],
        collect_results=True,
    )
    start = time.monotonic()
    await pipeline.run(list(range(10)))
    elapsed = time.monotonic() - start

    # 10 items at 5/s requires at least ~1 s; give generous margin for CI
    assert elapsed >= 0.9, f"expected ≥ 0.9s, got {elapsed:.2f}s"


async def test_rate_limit_and_concurrency_limit_coexist():
    """A stage can have both call_concurrency and call_rate active simultaneously."""
    active = 0
    max_active = 0
    call_count = 0

    async def task(item):
        nonlocal active, max_active, call_count
        async with concurrency_limit():
            async with rate_limit():
                active += 1
                max_active = max(max_active, active)
                call_count += 1
                await asyncio.sleep(0.01)
                active -= 1
        return item

    pipeline = Pipeline(
        stages=[
            Stage(
                "s",
                workers=8,
                tasks=[task],
                call_concurrency=2,
                call_rate=20,
                call_rate_period=1.0,
            )
        ],
        collect_results=True,
    )
    results = await pipeline.run(list(range(8)))
    assert len(results) == 8
    assert max_active <= 2


# ---------------------------------------------------------------------------
# Integration: retry × rate_limit
# ---------------------------------------------------------------------------

async def test_rate_limit_each_retry_acquires_limiter():
    """
    Every attempt — including retries — passes through rate_limit().
    The limiter must not be bypassed or double-counted between attempts.
    """
    acquisitions: list[int] = []  # item id recorded at each acquisition
    attempt_counters: dict[int, int] = {}

    async def flaky_task(item: int) -> int:
        attempt_counters[item] = attempt_counters.get(item, 0) + 1
        async with rate_limit():
            acquisitions.append(item)
            if attempt_counters[item] < 3:
                raise ValueError("simulated transient failure")
            return item

    pipeline = Pipeline(
        stages=[
            Stage(
                "s",
                workers=1,
                tasks=[flaky_task],
                call_rate=20,
                call_rate_period=1.0,
                retry="per_task",
                task_attempts=4,
            )
        ],
        collect_results=True,
    )
    results = await pipeline.run([1, 2])

    # Both items eventually succeed
    assert len(results) == 2
    # Each item needed 3 attempts → 6 total acquisitions through rate_limit()
    assert len(acquisitions) == 6
    # Item 1 appears 3 times (attempts 1, 2, 3), item 2 likewise
    assert acquisitions.count(1) == 3
    assert acquisitions.count(2) == 3


# ---------------------------------------------------------------------------
# task_concurrency_limits — all items processed, N at a time
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_concurrency_limits_processes_all_items():
    """
    task_concurrency_limits={"fn": N} does NOT permanently block workers.
    All items are processed — N concurrently at a time, not just N total.
    """
    peak = 0
    active = 0

    async def slow_task(x):
        nonlocal peak, active
        active += 1
        if active > peak:
            peak = active
        await asyncio.sleep(0.05)
        active -= 1
        return x

    pipeline = Pipeline(stages=[
        Stage(
            "s",
            workers=20,
            tasks=[slow_task],
            task_concurrency_limits={"slow_task": 3},
        )
    ])
    results = await pipeline.run(list(range(20)))

    # All 20 items must complete — workers cycle through 3 at a time, not 3 total
    assert len(results) == 20
    # Concurrency was respected — never more than 3 simultaneous
    assert peak <= 3


# ---------------------------------------------------------------------------
# Integration: call spacing precision (sliding-window check)
# ---------------------------------------------------------------------------

async def test_rate_limit_post_burst_spacing():
    """
    The leaky bucket allows an initial burst of call_rate items, then spaces
    subsequent acquisitions by ≥ time_period/call_rate seconds each.

    With call_rate=5, time_period=1.0: first 5 go through immediately,
    every acquisition after that must wait ~0.2 s for the bucket to refill.
    """
    timestamps: list[float] = []

    async def task(item: int) -> int:
        async with rate_limit():
            timestamps.append(time.monotonic())
        return item

    pipeline = Pipeline(
        stages=[Stage("s", workers=10, tasks=[task], call_rate=5, call_rate_period=1.0)],
        collect_results=True,
    )
    await pipeline.run(list(range(15)))

    assert len(timestamps) == 15
    sorted_ts = sorted(timestamps)

    # After the initial burst of call_rate items the bucket is empty.
    # Each subsequent acquisition refills one token (~0.2 s), so consecutive
    # post-burst timestamps must be at least 0.8 × (1.0/5.0) = 0.16 s apart
    # (0.8 factor gives generous headroom for CI timing jitter).
    min_spacing = 1.0 / 5.0 * 0.8
    post_burst = sorted_ts[5:]
    for i in range(1, len(post_burst)):
        interval = post_burst[i] - post_burst[i - 1]
        assert interval >= min_spacing, (
            f"post-burst interval {i}: {interval:.3f}s < {min_spacing:.3f}s"
        )


# ---------------------------------------------------------------------------
# Integration: call_rate_has_capacity() — adaptive pattern
# ---------------------------------------------------------------------------

async def test_call_rate_has_capacity_outside_pipeline():
    """Returns True when no rate limiter is configured (no-limit == always free)."""
    assert call_rate_has_capacity() is True
    assert call_rate_has_capacity(amount=999) is True


async def test_call_rate_has_capacity_reflects_budget():
    """
    Inside a stage: True while budget is available, False once exhausted.
    Uses workers=1 so items are serialised and the budget state is deterministic.
    """
    readings: list[bool] = []

    async def task(item: int) -> int:
        # Sample capacity *before* acquiring so we observe depletion
        readings.append(call_rate_has_capacity())
        async with rate_limit():
            return item

    pipeline = Pipeline(
        stages=[
            Stage(
                "s",
                workers=1,
                tasks=[task],
                call_rate=2,
                call_rate_period=60.0,  # long window → budget stays exhausted
            )
        ],
        collect_results=True,
    )
    await pipeline.run(list(range(5)))

    # First two items see available budget
    assert readings[0] is True
    assert readings[1] is True
    # After 2 acquisitions the bucket is full; later items see no capacity
    assert any(r is False for r in readings[2:]), (
        "expected has_capacity()=False after budget exhausted"
    )
