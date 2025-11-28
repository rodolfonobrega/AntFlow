"""Tests for StatusTracker."""

import asyncio

import pytest

from antflow import Pipeline, Stage, StatusEvent, StatusTracker


async def simple_task(x: int) -> int:
    """Simple task that adds 1."""
    await asyncio.sleep(0.01)
    return x + 1


async def failing_task(x: int) -> int:
    """Task that fails for value 5."""
    await asyncio.sleep(0.01)
    if x == 5:
        raise ValueError(f"Failed for {x}")
    return x


async def always_failing(x: int) -> int:
    """Task that always fails."""
    await asyncio.sleep(0.01)
    raise ValueError("Always fails")


class TestStatusTracker:
    """Test cases for StatusTracker."""

    @pytest.mark.asyncio
    async def test_status_tracker_basic(self):
        """Test basic StatusTracker functionality."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(name="TestStage", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        results = await pipeline.run([1, 2, 3])

        assert len(results) == 3
        assert len(events) > 0

        assert tracker.get_stats()["completed"] == 3

    @pytest.mark.asyncio
    async def test_status_tracker_queued_event(self):
        """Test that items emit 'queued' status when enqueued."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        queued_events = [e for e in events if e.status == "queued"]
        assert len(queued_events) > 0
        assert queued_events[0].stage == "Stage1"

    @pytest.mark.asyncio
    async def test_status_tracker_in_progress_event(self):
        """Test that items emit 'in_progress' when worker picks them up."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        in_progress_events = [e for e in events if e.status == "in_progress"]
        assert len(in_progress_events) == 1
        assert in_progress_events[0].worker is not None
        assert "Stage1-W" in in_progress_events[0].worker

    @pytest.mark.asyncio
    async def test_status_tracker_completed_event(self):
        """Test that items emit 'completed' when stage finishes."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        completed_events = [e for e in events if e.status == "completed"]
        assert len(completed_events) == 1
        assert completed_events[0].stage == "Stage1"

    @pytest.mark.asyncio
    async def test_status_tracker_failed_event(self):
        """Test that items emit 'failed' when stage fails."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(
            name="Stage1",
            workers=1,
            tasks=[always_failing],
            retry="per_task",
            task_attempts=1
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        failed_events = [e for e in events if e.status == "failed"]
        assert len(failed_events) == 1
        assert failed_events[0].stage == "Stage1"
        assert "error" in failed_events[0].metadata

    @pytest.mark.asyncio
    async def test_status_tracker_get_by_status(self):
        """Test filtering items by status."""
        tracker = StatusTracker()

        stage = Stage(name="Stage1", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1, 2, 3])

        completed = tracker.get_by_status("completed")
        assert len(completed) == 3

        failed = tracker.get_by_status("failed")
        assert len(failed) == 0

    @pytest.mark.asyncio
    async def test_status_tracker_get_stats(self):
        """Test aggregate statistics."""
        tracker = StatusTracker()

        stage = Stage(
            name="Stage1",
            workers=1,
            tasks=[failing_task],
            retry="per_task",
            task_attempts=1
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1, 2, 5, 7])

        stats = tracker.get_stats()
        assert stats["completed"] == 3
        assert stats["failed"] == 1
        assert stats["queued"] == 0
        assert stats["in_progress"] == 0

    @pytest.mark.asyncio
    async def test_status_tracker_get_history(self):
        """Test getting full event history for an item."""
        tracker = StatusTracker()

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([42])

        history = tracker.get_history(0)
        assert len(history) > 0

        statuses = [e.status for e in history]
        assert "queued" in statuses
        assert "in_progress" in statuses
        assert "completed" in statuses

    @pytest.mark.asyncio
    async def test_status_tracker_multi_stage(self):
        """Test tracking items through multiple stages."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage1 = Stage(name="Stage1", workers=1, tasks=[simple_task])
        stage2 = Stage(name="Stage2", workers=1, tasks=[simple_task])

        pipeline = Pipeline(stages=[stage1, stage2], status_tracker=tracker)

        await pipeline.run([1])

        stage1_events = [e for e in events if e.stage == "Stage1"]
        stage2_events = [e for e in events if e.stage == "Stage2"]

        assert len(stage1_events) > 0
        assert len(stage2_events) > 0

        assert any(e.status == "completed" for e in stage1_events)
        assert any(e.status == "completed" for e in stage2_events)

    @pytest.mark.asyncio
    async def test_status_tracker_retry_events(self):
        """Test tracking retry attempts."""
        tracker = StatusTracker()
        events = []
        call_count = {"count": 0}

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        async def task_with_retry(x: int) -> int:
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise ValueError("Retry me")
            return x * 2

        stage = Stage(
            name="RetryStage",
            workers=1,
            tasks=[task_with_retry],
            retry="per_stage",
            stage_attempts=3
        )

        pipeline = Pipeline(stages=[stage], status_tracker=tracker)
        await pipeline.run([1])

        retry_queued_events = [
            e for e in events
            if e.status == "queued" and e.metadata.get("retry")
        ]

        assert len(retry_queued_events) > 0
        assert retry_queued_events[0].metadata.get("attempt") == 2

    @pytest.mark.asyncio
    async def test_pipeline_without_tracker(self):
        """Test that pipeline works without tracker (backward compatible)."""
        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        results = await pipeline.run([1, 2, 3])

        assert len(results) == 3
        assert all(r.value == r.id + 2 for r in results)

    @pytest.mark.asyncio
    async def test_status_tracker_with_callback(self):
        """Test StatusTracker with on_status_change callback."""
        events = []

        async def on_change(event):
            events.append(event)

        tracker = StatusTracker(on_status_change=on_change)

        stage = Stage(
            name="Stage1",
            workers=1,
            tasks=[simple_task]
        )

        pipeline = Pipeline(stages=[stage], status_tracker=tracker)
        await pipeline.run([1])

        assert len(events) > 0
        assert any(e.status == "completed" for e in events)

    @pytest.mark.asyncio
    async def test_status_tracker_get_status(self):
        """Test getting current status of an item."""
        tracker = StatusTracker()

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([42])

        status = tracker.get_status(0)
        assert status is not None
        assert status.status == "completed"
        assert status.item_id == 0

    @pytest.mark.asyncio
    async def test_status_tracker_timestamps(self):
        """Test that events have valid timestamps."""
        tracker = StatusTracker()
        events = []

        async def on_change(event: StatusEvent):
            events.append(event)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        for event in events:
            assert event.timestamp > 0

        for i in range(len(events) - 1):
            assert events[i].timestamp <= events[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_worker_id_extraction(self):
        """Test worker_id property extraction from worker name."""
        tracker = StatusTracker()
        worker_ids = []

        async def on_change(event: StatusEvent):
            if event.worker_id is not None:
                worker_ids.append(event.worker_id)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=3, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1, 2, 3])

        assert len(worker_ids) > 0
        assert all(isinstance(wid, int) for wid in worker_ids)
        assert all(0 <= wid < 3 for wid in worker_ids)

    @pytest.mark.asyncio
    async def test_worker_id_tracking(self):
        """Test tracking items to workers."""
        from collections import defaultdict

        tracker = StatusTracker()
        item_to_worker = {}
        worker_activity = defaultdict(list)

        async def on_change(event: StatusEvent):
            if event.status == "in_progress" and event.worker_id is not None:
                item_to_worker[event.item_id] = event.worker_id
                worker_activity[event.worker_id].append(event.item_id)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1, 2, 3, 4])

        assert len(item_to_worker) == 4
        assert len(worker_activity) <= 2
        assert all(0 <= wid < 2 for wid in worker_activity.keys())

    @pytest.mark.asyncio
    async def test_custom_item_ids(self):
        """Test custom IDs in items."""
        tracker = StatusTracker()
        item_ids = []

        async def on_change(event: StatusEvent):
            if event.status == "queued":
                item_ids.append(event.item_id)

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        items = [
            {"id": "batch_0001", "value": 10},
            {"id": "batch_0002", "value": 20},
            {"id": "custom_id", "value": 30}
        ]

        await pipeline.run(items)

        assert "batch_0001" in item_ids
        assert "batch_0002" in item_ids
        assert "custom_id" in item_ids

    @pytest.mark.asyncio
    async def test_worker_utilization(self):
        """Test tracking worker activity."""
        from collections import defaultdict

        tracker = StatusTracker()
        worker_counts = defaultdict(int)

        async def on_change(event: StatusEvent):
            if event.status == "completed" and event.worker_id is not None:
                worker_counts[event.worker_id] += 1

        tracker.on_status_change = on_change

        stage = Stage(name="Stage1", workers=3, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run(range(15))

        total_completed = sum(worker_counts.values())
        assert total_completed == 15
        assert len(worker_counts) <= 3
        assert all(count > 0 for count in worker_counts.values())
