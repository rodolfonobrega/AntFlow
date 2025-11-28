"""Tests for Pipeline and Stage."""

import asyncio

import pytest

from antflow import Pipeline, PipelineError, Stage, StageValidationError


async def add_one(x: int) -> int:
    """Add 1 to input."""
    await asyncio.sleep(0.01)
    return x + 1


async def multiply_two(x: int) -> int:
    """Multiply input by 2."""
    await asyncio.sleep(0.01)
    return x * 2


async def failing_task(x: int) -> int:
    """Task that fails for specific values."""
    await asyncio.sleep(0.01)
    if x == 5:
        raise ValueError(f"Failed for {x}")
    return x


async def always_failing(x: int) -> int:
    """Task that always fails."""
    await asyncio.sleep(0.01)
    raise ValueError("Always fails")


class TestStage:
    """Test cases for Stage."""

    def test_stage_validation_invalid_retry(self):
        """Test stage validation with invalid retry policy."""
        stage = Stage(
            name="Test",
            workers=1,
            tasks=[add_one],
            retry="invalid"
        )

        with pytest.raises(StageValidationError, match="Invalid retry policy"):
            stage.validate()

    def test_stage_validation_zero_workers(self):
        """Test stage validation with zero workers."""
        stage = Stage(
            name="Test",
            workers=0,
            tasks=[add_one]
        )

        with pytest.raises(StageValidationError, match="must have at least 1 worker"):
            stage.validate()

    def test_stage_validation_no_tasks(self):
        """Test stage validation with no tasks."""
        stage = Stage(
            name="Test",
            workers=1,
            tasks=[]
        )

        with pytest.raises(StageValidationError, match="must have at least one task"):
            stage.validate()

    def test_stage_validation_success(self):
        """Test successful stage validation."""
        stage = Stage(
            name="Test",
            workers=2,
            tasks=[add_one, multiply_two],
            retry="per_task"
        )

        stage.validate()


class TestPipeline:
    """Test cases for Pipeline."""

    @pytest.mark.asyncio
    async def test_simple_pipeline(self):
        """Test a simple two-stage pipeline."""
        stage1 = Stage(name="Stage1", workers=2, tasks=[add_one])
        stage2 = Stage(name="Stage2", workers=2, tasks=[multiply_two])

        pipeline = Pipeline(stages=[stage1, stage2])
        results = await pipeline.run(range(10))

        assert len(results) == 10
        expected = [(i + 1) * 2 for i in range(10)]
        actual = [r.value for r in results]
        assert actual == expected

    @pytest.mark.asyncio
    async def test_pipeline_order_preservation(self):
        """Test that order is preserved."""
        stage = Stage(name="Stage", workers=3, tasks=[add_one])

        pipeline = Pipeline(stages=[stage])
        results = await pipeline.run(range(20))

        ids = [r.id for r in results]
        assert ids == list(range(20))

    @pytest.mark.asyncio
    async def test_pipeline_per_task_retry(self):
        """Test per-task retry strategy."""
        call_count = {"count": 0}

        async def task_with_retry(x: int) -> int:
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ValueError("Retry me")
            return x * 2

        stage = Stage(
            name="RetryStage",
            workers=1,
            tasks=[task_with_retry],
            retry="per_task",
            task_attempts=5,
            task_wait_seconds=0.01
        )

        pipeline = Pipeline(stages=[stage])
        results = await pipeline.run([1])

        assert len(results) == 1
        assert results[0].value == 2
        assert call_count["count"] >= 3

    @pytest.mark.asyncio
    async def test_pipeline_per_stage_retry(self):
        """Test per-stage retry strategy."""
        attempt_count = {"count": 0}

        async def stage_task(x: int) -> int:
            attempt_count["count"] += 1
            if attempt_count["count"] < 2:
                raise ValueError("Retry entire stage")
            return x * 3

        stage = Stage(
            name="StageRetry",
            workers=1,
            tasks=[stage_task],
            retry="per_stage",
            stage_attempts=3
        )

        pipeline = Pipeline(stages=[stage])
        results = await pipeline.run([5])

        assert len(results) == 1
        assert results[0].value == 15

    @pytest.mark.asyncio
    async def test_pipeline_collect_results_false(self):
        """Test pipeline with collect_results=False."""
        stage = Stage(name="Stage", workers=2, tasks=[add_one])

        pipeline = Pipeline(stages=[stage], collect_results=False)
        results = await pipeline.run(range(5))

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_pipeline_get_stats(self):
        """Test getting pipeline statistics."""
        stage = Stage(name="Stage", workers=2, tasks=[add_one])

        pipeline = Pipeline(stages=[stage])
        await pipeline.run(range(10))

        stats = pipeline.get_stats()
        assert stats.items_processed == 10
        assert stats.items_in_flight == 0
        assert "Stage" in stats.queue_sizes

    @pytest.mark.asyncio
    async def test_pipeline_callbacks(self):
        """Test pipeline with StatusTracker."""
        from antflow import StatusTracker

        success_calls = []
        failure_calls = []

        async def on_status_change(event):
            if event.status == "completed":
                success_calls.append(event.item_id)
            elif event.status == "failed":
                failure_calls.append(event.item_id)

        tracker = StatusTracker(on_status_change=on_status_change)

        stage = Stage(
            name="CallbackStage",
            workers=1,
            tasks=[failing_task],
            retry="per_task",
            task_attempts=1
        )

        pipeline = Pipeline(stages=[stage], status_tracker=tracker)
        await pipeline.run([1, 2, 5, 7])

        assert 0 in success_calls
        assert 1 in success_calls
        assert 2 in failure_calls
        assert 3 in success_calls



    @pytest.mark.asyncio
    async def test_pipeline_context_manager(self):
        """Test pipeline as context manager."""
        stage = Stage(name="Stage", workers=2, tasks=[add_one])

        async with Pipeline(stages=[stage]) as pipeline:
            results = await pipeline.run(range(5))
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_empty_pipeline_raises(self):
        """Test that empty pipeline raises error."""
        with pytest.raises(PipelineError, match="must have at least one stage"):
            Pipeline(stages=[])

    @pytest.mark.asyncio
    async def test_pipeline_with_dict_input(self):
        """Test pipeline with dict input items."""
        stage = Stage(name="Stage", workers=1, tasks=[add_one])

        pipeline = Pipeline(stages=[stage])
        items = [{"id": i, "value": i} for i in range(5)]
        results = await pipeline.run(items)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.id == i
            assert result.value == i + 1

    @pytest.mark.asyncio
    async def test_get_worker_names(self):
        """Test getting worker names from pipeline."""
        stage1 = Stage(name="Fetch", workers=3, tasks=[add_one])
        stage2 = Stage(name="Process", workers=2, tasks=[multiply_two])

        pipeline = Pipeline(stages=[stage1, stage2])
        worker_names = pipeline.get_worker_names()

        assert "Fetch" in worker_names
        assert "Process" in worker_names
        assert len(worker_names["Fetch"]) == 3
        assert len(worker_names["Process"]) == 2
        assert worker_names["Fetch"] == ["Fetch-W0", "Fetch-W1", "Fetch-W2"]
        assert worker_names["Process"] == ["Process-W0", "Process-W1"]
