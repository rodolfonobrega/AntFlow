"""Integration tests for AntFlow."""

import asyncio

import pytest

from antflow import AsyncExecutor, Pipeline, Stage


async def fetch_data(item_id: int) -> dict:
    """Simulate fetching data."""
    await asyncio.sleep(0.01)
    return {"id": item_id, "data": f"raw_{item_id}"}


async def process_data(data: dict) -> dict:
    """Process fetched data."""
    await asyncio.sleep(0.01)
    data["processed"] = True
    return data


async def save_data(data: dict) -> dict:
    """Save processed data."""
    await asyncio.sleep(0.01)
    data["saved"] = True
    return data


class TestIntegration:
    """Integration tests combining executor and pipeline."""

    @pytest.mark.asyncio
    async def test_executor_with_pipeline_workflow(self):
        """Test using executor to feed a pipeline."""
        async def create_pipeline_input(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        async with AsyncExecutor(max_workers=3) as executor:
            prepared_items = []
            async for result in executor.map(create_pipeline_input, range(10)):
                prepared_items.append(result)

        stage = Stage(
            name="Processing",
            workers=2,
            tasks=[fetch_data, process_data, save_data]
        )

        pipeline = Pipeline(stages=[stage])
        results = await pipeline.run(prepared_items)

        assert len(results) == 10
        for result in results:
            assert result.value['processed'] is True
            assert result.value['saved'] is True

    @pytest.mark.asyncio
    async def test_multi_stage_etl_pipeline(self):
        """Test a complete ETL pipeline with multiple stages."""
        extract_stage = Stage(
            name="Extract",
            workers=3,
            tasks=[fetch_data],
            retry="per_task",
            task_attempts=3
        )

        transform_stage = Stage(
            name="Transform",
            workers=2,
            tasks=[process_data],
            retry="per_task",
            task_attempts=2
        )

        load_stage = Stage(
            name="Load",
            workers=2,
            tasks=[save_data],
            retry="per_stage",
            stage_attempts=2
        )

        pipeline = Pipeline(
            stages=[extract_stage, transform_stage, load_stage]
        )

        results = await pipeline.run(range(20))

        assert len(results) == 20

        for i, result in enumerate(results):
            assert result.id == i
            value = result.value
            assert value['id'] == i
            assert value['processed'] is True
            assert value['saved'] is True

    @pytest.mark.asyncio
    async def test_pipeline_with_callbacks_and_metrics(self):
        """Test pipeline with StatusTracker and metrics tracking."""
        from antflow import StatusTracker

        success_count = {"count": 0}
        failure_count = {"count": 0}

        async def on_status_change(event):
            if event.status == "completed":
                success_count["count"] += 1
            elif event.status == "failed":
                failure_count["count"] += 1

        async def sometimes_fails(x: int) -> int:
            if x % 5 == 0:
                raise ValueError(f"Failed for {x}")
            return x * 2

        tracker = StatusTracker(on_status_change=on_status_change)

        stage = Stage(
            name="RiskyStage",
            workers=2,
            tasks=[sometimes_fails],
            retry="per_task",
            task_attempts=1
        )

        pipeline = Pipeline(stages=[stage], status_tracker=tracker)
        results = await pipeline.run(range(10))

        stats = pipeline.get_stats()
        tracker_stats = tracker.get_stats()

        assert success_count["count"] > 0
        assert failure_count["count"] > 0
        assert stats.items_processed + stats.items_failed == 10
        assert len(results) < 10
        assert tracker_stats["completed"] == success_count["count"]
        assert tracker_stats["failed"] == failure_count["count"]

    @pytest.mark.asyncio
    async def test_dynamic_pipeline_modification(self):
        """Test dynamically modifying pipeline structure."""
        stage1 = Stage(name="Stage1", workers=1, tasks=[fetch_data])

        pipeline = Pipeline(stages=[stage1])

        stage2 = Stage(name="Stage2", workers=1, tasks=[process_data])
        await pipeline.add_stage(stage2)

        stage3 = Stage(name="Stage3", workers=1, tasks=[save_data])
        await pipeline.add_stage(stage3)

        results = await pipeline.run(range(5))

        assert len(results) == 5
        for result in results:
            assert result.value['processed'] is True
            assert result.value['saved'] is True

    @pytest.mark.asyncio
    async def test_large_scale_processing(self):
        """Test processing a large number of items."""
        async def quick_task(x: int) -> int:
            return x + 1

        stage = Stage(
            name="QuickStage",
            workers=10,
            tasks=[quick_task],
            retry="per_task",
            task_attempts=1
        )

        pipeline = Pipeline(stages=[stage])

        num_items = 1000
        results = await pipeline.run(range(num_items))

        assert len(results) == num_items

        values = [r.value for r in results]
        expected = [i + 1 for i in range(num_items)]
        assert values == expected
