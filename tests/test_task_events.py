"""Tests for task-level event tracking."""

import asyncio

import pytest

from antflow import Pipeline, Stage, StatusTracker, TaskEvent


async def simple_task(x: int) -> int:
    """Simple task that always succeeds."""
    await asyncio.sleep(0.01)
    return x * 2


async def failing_task(x: int) -> int:
    """Task that always fails."""
    await asyncio.sleep(0.01)
    raise ValueError(f"Task failed for {x}")


async def flaky_task(x: int) -> int:
    """Task that fails first time but succeeds on retry."""
    await asyncio.sleep(0.01)
    if not hasattr(flaky_task, "_attempts"):
        flaky_task._attempts = {}

    flaky_task._attempts[x] = flaky_task._attempts.get(x, 0) + 1

    if flaky_task._attempts[x] == 1:
        raise RuntimeError(f"Temporary failure for {x}")

    return x * 3


class TestTaskEvents:
    """Test cases for task-level event tracking."""

    @pytest.mark.asyncio
    async def test_task_complete_event(self):
        """Test that task complete events are emitted."""
        events = []

        async def on_task_complete(event: TaskEvent):
            events.append(event)

        tracker = StatusTracker(on_task_complete=on_task_complete)
        stage = Stage(name="Test", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([5])

        assert len(events) == 1
        assert events[0].event_type == "complete"
        assert events[0].task_name == "simple_task"
        assert events[0].item_id == 0
        assert events[0].attempt == 1
        assert events[0].duration is not None
        assert events[0].duration > 0
        assert events[0].error is None

    @pytest.mark.asyncio
    async def test_task_start_event(self):
        """Test that task start events are emitted."""
        events = []

        async def on_task_start(event: TaskEvent):
            events.append(event)

        tracker = StatusTracker(on_task_start=on_task_start)
        stage = Stage(name="Test", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([10])

        assert len(events) == 1
        assert events[0].event_type == "start"
        assert events[0].task_name == "simple_task"
        assert events[0].attempt == 1
        assert events[0].duration is None

    @pytest.mark.asyncio
    async def test_task_retry_event(self):
        """Test that task retry events are emitted."""
        events = []
        flaky_task._attempts = {}

        async def on_task_retry(event: TaskEvent):
            events.append(event)

        tracker = StatusTracker(on_task_retry=on_task_retry)
        stage = Stage(
            name="Flaky",
            workers=1,
            tasks=[flaky_task],
            retry="per_task",
            task_attempts=3
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([7])

        assert len(events) == 1
        assert events[0].event_type == "retry"
        assert events[0].task_name == "flaky_task"
        assert events[0].attempt == 1
        assert events[0].error is not None
        assert isinstance(events[0].error, RuntimeError)
        assert events[0].duration is not None

    @pytest.mark.asyncio
    async def test_task_fail_event(self):
        """Test that task fail events are emitted."""
        events = []

        async def on_task_fail(event: TaskEvent):
            events.append(event)

        tracker = StatusTracker(on_task_fail=on_task_fail)
        stage = Stage(
            name="Failing",
            workers=1,
            tasks=[failing_task],
            retry="per_task",
            task_attempts=2
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([3])

        assert len(events) == 1
        assert events[0].event_type == "fail"
        assert events[0].task_name == "failing_task"
        assert events[0].attempt == 2
        assert events[0].error is not None
        assert isinstance(events[0].error, ValueError)

    @pytest.mark.asyncio
    async def test_multiple_tasks_events(self):
        """Test events for multiple tasks in a stage."""
        events = {"start": [], "complete": []}

        async def on_start(event: TaskEvent):
            events["start"].append(event)

        async def on_complete(event: TaskEvent):
            events["complete"].append(event)

        tracker = StatusTracker(
            on_task_start=on_start,
            on_task_complete=on_complete
        )

        stage = Stage(
            name="Multi",
            workers=1,
            tasks=[simple_task, simple_task],
            retry="per_task",
            task_attempts=1
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        assert len(events["start"]) == 2
        assert len(events["complete"]) == 2

        assert events["start"][0].task_name == "simple_task"
        assert events["start"][1].task_name == "simple_task"

    @pytest.mark.asyncio
    async def test_all_task_callbacks(self):
        """Test that all task callbacks work together."""
        events = {
            "start": [],
            "complete": [],
            "retry": [],
            "fail": []
        }

        async def on_start(event):
            events["start"].append(event)

        async def on_complete(event):
            events["complete"].append(event)

        async def on_retry(event):
            events["retry"].append(event)

        async def on_fail(event):
            events["fail"].append(event)

        tracker = StatusTracker(
            on_task_start=on_start,
            on_task_complete=on_complete,
            on_task_retry=on_retry,
            on_task_fail=on_fail
        )

        stage = Stage(
            name="Test",
            workers=1,
            tasks=[failing_task],
            retry="per_task",
            task_attempts=3
        )
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([1])

        assert len(events["start"]) == 3
        assert len(events["complete"]) == 0
        assert len(events["retry"]) == 2
        assert len(events["fail"]) == 1

    @pytest.mark.asyncio
    async def test_task_event_fields(self):
        """Test that task event contains all expected fields."""
        event_captured = None

        async def on_complete(event: TaskEvent):
            nonlocal event_captured
            event_captured = event

        tracker = StatusTracker(on_task_complete=on_complete)
        stage = Stage(name="TestStage", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        await pipeline.run([42])

        assert event_captured is not None
        assert event_captured.item_id == 0
        assert event_captured.stage == "TestStage"
        assert event_captured.task_name == "simple_task"
        assert event_captured.worker == "TestStage-W0"
        assert event_captured.event_type == "complete"
        assert event_captured.attempt == 1
        assert event_captured.timestamp > 0
        assert event_captured.duration > 0
        assert event_captured.error is None

    @pytest.mark.asyncio
    async def test_no_tracker_no_events(self):
        """Test that pipeline works without task event tracker."""
        stage = Stage(name="Test", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        results = await pipeline.run([1, 2, 3])

        assert len(results) == 3
