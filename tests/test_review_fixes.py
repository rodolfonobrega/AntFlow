"""Regression tests for bugs found in the v0.8.0 code review.

Each test maps to a numbered finding from the review:
  #1 pull-stage double-count in get_stats
  #2 _PULL_CLOSED / RendezvousChannel.task_done underflow
  #3 StatusTracker.get_stats KeyError on retrying/skipped
  #4 join() race losing per_stage retries
  #6 full dashboard assuming integer item IDs
  #7 stage-weighted progress in dashboards
  #8 as_completed leak / timeout behaviour
"""

import asyncio
import time

import pytest

from antflow import AsyncExecutor, Pipeline, Stage, StatusTracker
from antflow.display.base import BaseDashboard
from antflow.pipeline import _PULL_CLOSED, RendezvousChannel
from antflow.types import (
    DashboardSnapshot,
    ErrorSummary,
    PipelineStats,
    StageStats,
    StatusEvent,
)


# --------------------------------------------------------------------------- #
# #1 — pull stage must not count in-flight items as "pending"
# --------------------------------------------------------------------------- #
async def test_pull_stage_no_double_count_in_stats():
    started = asyncio.Event()
    release = asyncio.Event()

    async def produce(x):
        return x

    async def consume(x):
        started.set()
        await release.wait()
        return x

    pipeline = Pipeline(stages=[
        Stage("produce", workers=2, tasks=[produce]),
        Stage("consume", workers=2, tasks=[consume], pull=True),
    ])
    await pipeline.start()
    await pipeline.feed(list(range(6)))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        await asyncio.sleep(0.05)  # let both consume workers pick up an item

        consume_stats = pipeline.get_stats().stage_stats["consume"]
        # Zero-buffer channel: items being processed are reported via busy
        # workers (in_progress), never as pending.
        assert consume_stats.pending_items == 0
        assert consume_stats.in_progress_items >= 1
    finally:
        release.set()
        await pipeline.join()


# --------------------------------------------------------------------------- #
# #2 — RendezvousChannel counter must never go negative
# --------------------------------------------------------------------------- #
async def test_rendezvous_task_done_no_underflow():
    ch = RendezvousChannel()
    ch.task_done()  # nothing was ever delivered
    ch.task_done()
    assert ch.qsize() == 0
    assert ch.empty()


async def test_rendezvous_close_then_get_returns_sentinel():
    ch = RendezvousChannel()
    ch.close()
    assert await ch.get() is _PULL_CLOSED
    assert ch.qsize() == 0


async def test_pull_pipeline_shutdown_no_negative_qsize():
    release = asyncio.Event()

    async def produce(x):
        return x

    async def consume(x):
        await release.wait()
        return x

    # 1 item, 3 workers -> 1 worker busy, 2 idle waiting on get() and so will
    # receive _PULL_CLOSED on shutdown.
    pipeline = Pipeline(stages=[
        Stage("produce", workers=1, tasks=[produce]),
        Stage("consume", workers=3, tasks=[consume], pull=True),
    ])
    await pipeline.start()
    await pipeline.feed([1])
    await asyncio.sleep(0.1)
    release.set()
    await pipeline.shutdown()

    for q in pipeline._queues:
        assert q.qsize() >= 0


# --------------------------------------------------------------------------- #
# #3 — get_stats must handle every StatusType
# --------------------------------------------------------------------------- #
def test_tracker_get_stats_covers_all_statuses():
    tracker = StatusTracker()
    for status in ("queued", "in_progress", "completed", "failed", "retrying", "skipped"):
        tracker._current_status[status] = StatusEvent(
            item_id=status, stage="s", status=status, worker=None, timestamp=time.time()
        )
    stats = tracker.get_stats()  # must not raise KeyError
    assert stats["retrying"] == 1
    assert stats["skipped"] == 1
    assert stats["completed"] == 1


async def test_tracker_get_stats_with_skipped_items():
    tracker = StatusTracker()

    async def noop(x):
        return x

    pipeline = Pipeline(
        stages=[Stage("S", workers=2, tasks=[noop], skip_if=lambda v: v % 2 == 0)],
        status_tracker=tracker,
    )
    await pipeline.run(list(range(4)))

    stats = tracker.get_stats()  # would KeyError before the fix
    assert stats["skipped"] == 2


# --------------------------------------------------------------------------- #
# #4 — per_stage retries must not be dropped by join()
# --------------------------------------------------------------------------- #
async def test_per_stage_retry_no_lost_items():
    attempts: dict[int, int] = {}

    async def flaky(x):
        attempts[x] = attempts.get(x, 0) + 1
        if attempts[x] < 2:
            raise ValueError("fail once")
        return x

    pipeline = Pipeline(stages=[
        Stage("S", workers=4, tasks=[flaky], retry="per_stage", stage_attempts=3),
    ])
    results = await pipeline.run(list(range(20)))

    assert sorted(r.value for r in results) == list(range(20))


# --------------------------------------------------------------------------- #
# #6 — tracker exposes the real item IDs (not assumed to be range(0, N))
# --------------------------------------------------------------------------- #
async def test_get_tracked_ids_with_string_ids():
    tracker = StatusTracker()

    async def up(x):
        return x

    items = [{"id": f"item-{i}", "value": i} for i in range(3)]
    pipeline = Pipeline(stages=[Stage("S", workers=2, tasks=[up])], status_tracker=tracker)
    await pipeline.run(items)

    ids = set(tracker.get_tracked_ids())
    assert ids == {"item-0", "item-1", "item-2"}
    # None of these match range(0, 3), so the old dashboard loop would miss them all.
    assert all(isinstance(i, str) for i in ids)


# --------------------------------------------------------------------------- #
# #7 — progress is weighted by per-stage completions, not just final output
# --------------------------------------------------------------------------- #
def test_progress_units_reflects_intermediate_stages():
    stage_stats = {
        "A": StageStats("A", 0, 0, 10, 0),  # all 10 done with stage A
        "B": StageStats("B", 0, 0, 5, 0),   # half-way through stage B
        "C": StageStats("C", 0, 0, 0, 0),   # nothing reached stage C yet
    }
    snapshot = DashboardSnapshot(
        worker_states={},
        worker_metrics={},
        pipeline_stats=PipelineStats(
            items_processed=0,  # final output is still 0 -> old % would show 0%
            items_failed=0,
            items_in_flight=0,
            queue_sizes={},
            stage_stats=stage_stats,
        ),
        error_summary=ErrorSummary(0, {}, {}, []),
        timestamp=0.0,
    )

    done_units, total_units = BaseDashboard._progress_units(snapshot, total_items=10)
    assert total_units == 30  # 10 items * 3 stages
    assert done_units == 15   # 10 + 5 + 0  -> 50%, not 0%


# --------------------------------------------------------------------------- #
# #8 — as_completed yields all and honours timeout without leaking
# --------------------------------------------------------------------------- #
async def test_as_completed_yields_all():
    async with AsyncExecutor(max_workers=3) as ex:
        async def work(x):
            await asyncio.sleep(0.01 * x)
            return x

        futures = [ex.submit(work, i) for i in range(5)]
        got = [await f.result() async for f in ex.as_completed(futures)]
        assert sorted(got) == [0, 1, 2, 3, 4]


async def test_as_completed_timeout_raises():
    async with AsyncExecutor(max_workers=1) as ex:
        async def slow(x):
            await asyncio.sleep(1)
            return x

        futures = [ex.submit(slow, i) for i in range(3)]
        with pytest.raises(asyncio.TimeoutError):
            async for _ in ex.as_completed(futures, timeout=0.05):
                pass
