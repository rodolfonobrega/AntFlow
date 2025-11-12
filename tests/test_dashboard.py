"""Tests for dashboard functionality."""

import asyncio

import pytest

from antflow import Pipeline, PipelineDashboard, Stage, StatusTracker


async def simple_task(x: int) -> int:
    """Simple test task."""
    await asyncio.sleep(0.01)
    return x * 2


async def failing_task(x: int) -> int:
    """Task that fails for specific values."""
    await asyncio.sleep(0.01)
    if x == 5:
        raise ValueError(f"Failed for {x}")
    return x


class TestWorkerStates:
    """Test cases for worker state tracking."""

    @pytest.mark.asyncio
    async def test_get_worker_states_initial(self):
        """Test that worker states are initialized correctly."""
        stage = Stage(name="Test", workers=3, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        states = pipeline.get_worker_states()

        assert len(states) == 3
        assert "Test-W0" in states
        assert "Test-W1" in states
        assert "Test-W2" in states

        for state in states.values():
            assert state.status == "idle"
            assert state.current_item_id is None
            assert state.processing_since is None

    @pytest.mark.asyncio
    async def test_worker_states_after_processing(self):
        """Test that worker states return to idle after processing."""
        stage = Stage(name="Process", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        await pipeline.run(range(10))

        states_after = pipeline.get_worker_states()

        for state in states_after.values():
            assert state.status == "idle"
            assert state.current_item_id is None
            assert state.processing_since is None


class TestWorkerMetrics:
    """Test cases for worker metrics."""

    @pytest.mark.asyncio
    async def test_get_worker_metrics_initial(self):
        """Test that worker metrics are initialized correctly."""
        stage = Stage(name="Test", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        metrics = pipeline.get_worker_metrics()

        assert len(metrics) == 2
        assert "Test-W0" in metrics
        assert "Test-W1" in metrics

        for metric in metrics.values():
            assert metric.items_processed == 0
            assert metric.items_failed == 0
            assert metric.total_processing_time == 0.0
            assert metric.last_active is None

    @pytest.mark.asyncio
    async def test_worker_metrics_after_processing(self):
        """Test that worker metrics are updated after processing."""
        stage = Stage(name="Process", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        await pipeline.run(range(10))

        metrics = pipeline.get_worker_metrics()

        total_processed = sum(m.items_processed for m in metrics.values())
        assert total_processed == 10

        for metric in metrics.values():
            if metric.items_processed > 0:
                assert metric.avg_processing_time > 0
                assert metric.last_active is not None

    @pytest.mark.asyncio
    async def test_worker_metrics_with_failures(self):
        """Test that worker metrics track failures."""
        stage = Stage(
            name="Failing",
            workers=1,
            tasks=[failing_task],
            retry="per_task",
            task_attempts=1
        )
        pipeline = Pipeline(stages=[stage])

        await pipeline.run(range(10))

        metrics = pipeline.get_worker_metrics()

        total_failed = sum(m.items_failed for m in metrics.values())
        assert total_failed > 0


class TestDashboardSnapshot:
    """Test cases for dashboard snapshot."""

    @pytest.mark.asyncio
    async def test_get_dashboard_snapshot(self):
        """Test getting complete dashboard snapshot."""
        stage = Stage(name="Test", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage])

        await pipeline.run(range(5))

        snapshot = pipeline.get_dashboard_snapshot()

        assert len(snapshot.worker_states) == 2
        assert len(snapshot.worker_metrics) == 2
        assert snapshot.pipeline_stats.items_processed == 5
        assert snapshot.timestamp > 0


class TestPipelineDashboard:
    """Test cases for PipelineDashboard class."""

    @pytest.mark.asyncio
    async def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        dashboard = PipelineDashboard(pipeline, tracker)

        assert dashboard.pipeline is pipeline
        assert dashboard.tracker is tracker

    @pytest.mark.asyncio
    async def test_dashboard_get_snapshot(self):
        """Test getting snapshot from dashboard."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        dashboard = PipelineDashboard(pipeline, tracker)

        snapshot = dashboard.get_snapshot()

        assert len(snapshot.worker_states) == 2
        assert len(snapshot.worker_metrics) == 2

    @pytest.mark.asyncio
    async def test_dashboard_get_active_workers(self):
        """Test getting active workers."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=3, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        dashboard = PipelineDashboard(pipeline, tracker)

        active_before = dashboard.get_active_workers()
        assert len(active_before) == 0

        idle_before = dashboard.get_idle_workers()
        assert len(idle_before) == 3

    @pytest.mark.asyncio
    async def test_dashboard_subscribe(self):
        """Test subscribing to dashboard events."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        dashboard = PipelineDashboard(pipeline, tracker)

        events = []

        async def on_event(event):
            events.append(event)

        dashboard.subscribe(on_event)

        await pipeline.run(range(3))

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_dashboard_get_worker_utilization(self):
        """Test getting worker utilization."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        dashboard = PipelineDashboard(pipeline, tracker)

        util_before = dashboard.get_worker_utilization()
        assert all(u == 0.0 for u in util_before.values())

        await pipeline.run(range(10))

        util_after = dashboard.get_worker_utilization()
        assert all(u == 1.0 for u in util_after.values())

    @pytest.mark.asyncio
    async def test_dashboard_context_manager(self):
        """Test dashboard as context manager."""
        tracker = StatusTracker()
        stage = Stage(name="Test", workers=1, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage], status_tracker=tracker)

        updates = []

        async def on_update(snapshot):
            updates.append(snapshot)

        dashboard = PipelineDashboard(
            pipeline,
            tracker,
            on_update=on_update,
            update_interval=0.1
        )

        async with dashboard:
            await asyncio.sleep(0.25)

        assert len(updates) >= 2


class TestDynamicPipelineWithTracking:
    """Test that dynamic pipeline modifications update tracking."""

    @pytest.mark.asyncio
    async def test_add_stage_updates_tracking(self):
        """Test that adding a stage updates worker tracking."""
        stage1 = Stage(name="Stage1", workers=2, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage1])

        initial_states = pipeline.get_worker_states()
        assert len(initial_states) == 2

        stage2 = Stage(name="Stage2", workers=3, tasks=[simple_task])
        await pipeline.add_stage(stage2)

        updated_states = pipeline.get_worker_states()
        assert len(updated_states) == 5
        assert "Stage2-W0" in updated_states
        assert "Stage2-W1" in updated_states
        assert "Stage2-W2" in updated_states

    @pytest.mark.asyncio
    async def test_remove_stage_updates_tracking(self):
        """Test that removing a stage updates worker tracking."""
        stage1 = Stage(name="Stage1", workers=2, tasks=[simple_task])
        stage2 = Stage(name="Stage2", workers=3, tasks=[simple_task])
        pipeline = Pipeline(stages=[stage1, stage2])

        initial_states = pipeline.get_worker_states()
        assert len(initial_states) == 5

        await pipeline.remove_stage("Stage2")

        updated_states = pipeline.get_worker_states()
        assert len(updated_states) == 2
        assert "Stage2-W0" not in updated_states
        assert "Stage2-W1" not in updated_states
        assert "Stage2-W2" not in updated_states
