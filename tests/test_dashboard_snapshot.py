"""
Tests for DashboardSnapshot accuracy: worker counts, queue sizes,
stage stats, progress units, and item tracker.

These tests assert the *data* that feeds every dashboard — if the snapshot
is wrong, every dashboard variant will display wrong numbers.
"""
from __future__ import annotations

import asyncio

from antflow import Pipeline, Stage, StatusTracker
from antflow.display.base import BaseDashboard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SnapshotCapture:
    """Minimal custom dashboard that records every on_update snapshot."""

    def __init__(self):
        self.snapshots = []

    def on_start(self, pipeline, total_items):
        pass

    def on_update(self, snapshot):
        self.snapshots.append(snapshot)

    def on_finish(self, results, summary):
        pass


# ---------------------------------------------------------------------------
# 1. Worker count in snapshot matches Stage.workers
# ---------------------------------------------------------------------------

async def test_snapshot_worker_count_matches_stage():
    """snapshot.worker_states has exactly Stage.workers entries per stage."""
    barrier = asyncio.Event()

    async def blocking_task(x: int) -> int:
        await barrier.wait()
        return x

    pipeline = Pipeline(
        stages=[Stage("stage_a", workers=4, tasks=[blocking_task])],
        collect_results=True,
    )
    run = asyncio.create_task(pipeline.run(range(8)))
    await asyncio.sleep(0.1)

    snap = pipeline.get_dashboard_snapshot()
    workers_for_stage = [w for w in snap.worker_states.values() if w.stage == "stage_a"]
    assert len(workers_for_stage) == 4

    barrier.set()
    await run


# ---------------------------------------------------------------------------
# 2. pending_items and in_progress_items are accurate under load
# ---------------------------------------------------------------------------

async def test_snapshot_in_progress_and_pending():
    """
    With 2 workers and 5 items, while workers are blocked:
      in_progress_items == 2
      pending_items     == 3
    """
    barrier = asyncio.Event()

    async def blocking_task(x: int) -> int:
        await barrier.wait()
        return x

    pipeline = Pipeline(
        stages=[Stage("s", workers=2, tasks=[blocking_task])],
        collect_results=True,
    )
    run = asyncio.create_task(pipeline.run(range(5)))
    await asyncio.sleep(0.1)

    snap = pipeline.get_dashboard_snapshot()
    stage = snap.pipeline_stats.stage_stats["s"]
    assert stage.in_progress_items == 2, f"expected 2 in_progress, got {stage.in_progress_items}"
    assert stage.pending_items == 3, f"expected 3 pending, got {stage.pending_items}"

    busy = sum(1 for w in snap.worker_states.values() if w.stage == "s" and w.status == "busy")
    assert busy == 2

    barrier.set()
    await run


# ---------------------------------------------------------------------------
# 3. Pull stage (RendezvousChannel) never double-counts items
# ---------------------------------------------------------------------------

async def test_snapshot_pull_stage_no_double_count():
    """
    RendezvousChannel has zero buffer — pending_items for the pull stage must
    be 0.  items_in_flight must not exceed Stage.workers (double-count bug
    would give 2×workers).

    A pull stage cannot be the first stage, so we use a feeder stage.
    """
    barrier = asyncio.Event()

    async def feeder_task(x: int) -> int:
        return x

    async def blocking_task(x: int) -> int:
        await barrier.wait()
        return x

    pipeline = Pipeline(
        stages=[
            Stage("feeder", workers=4, tasks=[feeder_task]),
            Stage("pull_s", workers=3, tasks=[blocking_task], pull=True),
        ],
        collect_results=True,
    )
    run = asyncio.create_task(pipeline.run(range(6)))
    await asyncio.sleep(0.2)

    snap = pipeline.get_dashboard_snapshot()
    stage = snap.pipeline_stats.stage_stats["pull_s"]

    # No buffer → pending must be 0 (was incorrectly equal to in_progress before the fix)
    assert stage.pending_items == 0, (
        f"pull stage should have pending=0, got {stage.pending_items}"
    )
    # in_flight must not exceed worker count (double-count bug would give 2×workers)
    pull_in_flight = stage.in_progress_items + stage.pending_items
    assert pull_in_flight <= 3, (
        f"pull stage effective in_flight={pull_in_flight} exceeds workers=3"
    )

    barrier.set()
    await run


# ---------------------------------------------------------------------------
# 4. _progress_units grows monotonically in a multi-stage pipeline
# ---------------------------------------------------------------------------

async def test_snapshot_progress_units_monotonic_multi_stage():
    """
    In a 3-stage pipeline, stage-weighted done_units must never decrease
    between consecutive snapshots.

    Uses dashboard_update_interval=0.05 and 50ms tasks so the monitor fires
    several times during execution.
    """
    capture = SnapshotCapture()

    async def slow_task(x: int) -> int:
        await asyncio.sleep(0.05)
        return x

    total = 20
    pipeline = Pipeline(
        stages=[
            Stage("a", workers=3, tasks=[slow_task]),
            Stage("b", workers=3, tasks=[slow_task]),
            Stage("c", workers=3, tasks=[slow_task]),
        ],
        collect_results=True,
    )
    await pipeline.run(
        range(total),
        custom_dashboard=capture,
        dashboard_update_interval=0.05,
    )

    assert len(capture.snapshots) > 1, (
        f"expected multiple on_update calls, got {len(capture.snapshots)}"
    )

    prev_done = -1
    for snap in capture.snapshots:
        done, total_units = BaseDashboard._progress_units(snap, total)
        assert done >= prev_done, (
            f"progress went backwards: {done} < {prev_done}"
        )
        assert 0 <= done <= total_units
        prev_done = done


# ---------------------------------------------------------------------------
# 5. completed_items increments and never exceeds total items
# ---------------------------------------------------------------------------

async def test_snapshot_completed_items_never_exceeds_total():
    """
    Across all snapshots, completed_items in each stage must be ≤ total items
    and must increase (never decrease).
    """
    capture = SnapshotCapture()

    async def fast_task(x: int) -> int:
        await asyncio.sleep(0.005)
        return x

    total = 15
    pipeline = Pipeline(
        stages=[Stage("s", workers=4, tasks=[fast_task])],
        collect_results=True,
    )
    await pipeline.run(range(total), custom_dashboard=capture)

    prev_completed = -1
    for snap in capture.snapshots:
        completed = snap.pipeline_stats.stage_stats["s"].completed_items
        assert completed >= prev_completed
        assert completed <= total
        prev_completed = completed


# ---------------------------------------------------------------------------
# 6. String IDs tracked correctly (full dashboard items panel)
# ---------------------------------------------------------------------------

async def test_snapshot_string_item_ids_tracked():
    """
    Items with non-integer IDs (strings) must appear in StatusTracker
    with the correct status — not all PENDING (bug #6 regression).

    Custom IDs are passed as dicts with an "id" key, which is how
    Pipeline._prepare_payload() honours a user-supplied identifier.
    """
    async def fast_task(x: str) -> str:
        await asyncio.sleep(0.01)
        return x.upper()

    tracker = StatusTracker()
    pipeline = Pipeline(
        stages=[Stage("s", workers=2, tasks=[fast_task])],
        status_tracker=tracker,
        collect_results=True,
    )
    string_ids = ["alpha", "beta", "gamma", "delta"]
    # Wrap as dicts so the pipeline uses our string as the item_id
    items = [{"id": sid, "value": sid} for sid in string_ids]
    results = await pipeline.run(items)

    assert len(results) == 4

    tracked_ids = tracker.get_tracked_ids()
    assert set(tracked_ids) == set(string_ids), (
        f"tracked IDs {tracked_ids!r} don't match expected {string_ids!r}"
    )

    # Every item must end up as completed — none should be PENDING/missing
    for item_id in string_ids:
        event = tracker.get_status(item_id)
        assert event is not None, f"item {item_id!r} has no status event"
        assert event.status == "completed", (
            f"item {item_id!r}: expected 'completed', got {event.status!r}"
        )


# ---------------------------------------------------------------------------
# 7. items_in_flight returns to 0 after pipeline finishes
# ---------------------------------------------------------------------------

async def test_snapshot_in_flight_zero_after_completion():
    """After pipeline.run() returns, items_in_flight must be 0."""
    async def fast_task(x: int) -> int:
        return x

    pipeline = Pipeline(
        stages=[Stage("s", workers=3, tasks=[fast_task])],
        collect_results=True,
    )
    await pipeline.run(range(10))

    snap = pipeline.get_dashboard_snapshot()
    assert snap.pipeline_stats.items_in_flight == 0
    assert snap.pipeline_stats.items_processed == 10
