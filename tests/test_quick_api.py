"""Tests for Pipeline.quick() and PipelineBuilder APIs."""

import asyncio

import pytest

from antflow import Pipeline


async def double(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


async def add_one(x: int) -> int:
    await asyncio.sleep(0.01)
    return x + 1


async def to_string(x: int) -> str:
    await asyncio.sleep(0.01)
    return f"result_{x}"


class TestPipelineQuick:
    """Tests for Pipeline.quick() class method."""

    @pytest.mark.asyncio
    async def test_quick_single_task(self):
        """Quick pipeline with single task."""
        items = list(range(10))
        results = await Pipeline.quick(items, double, workers=3)

        assert len(results) == 10
        values = [r.value for r in results]
        assert sorted(values) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    @pytest.mark.asyncio
    async def test_quick_multiple_tasks(self):
        """Quick pipeline with multiple tasks creates one stage per task."""
        items = list(range(5))
        results = await Pipeline.quick(items, [double, add_one], workers=2)

        assert len(results) == 5
        values = sorted([r.value for r in results])
        assert values == [1, 3, 5, 7, 9]

    @pytest.mark.asyncio
    async def test_quick_with_retries(self):
        """Quick pipeline respects retries parameter."""
        call_count = {"count": 0}

        async def flaky_task(x):
            call_count["count"] += 1
            if call_count["count"] <= 2:
                raise ValueError("Flaky error")
            return x * 2

        results = await Pipeline.quick([1], flaky_task, workers=1, retries=5)

        assert len(results) == 1
        assert results[0].value == 2


class TestPipelineBuilder:
    """Tests for PipelineBuilder fluent API."""

    @pytest.mark.asyncio
    async def test_builder_basic(self):
        """Basic builder usage."""
        results = await (
            Pipeline.create()
            .add("Stage1", double, workers=2)
            .run(list(range(5)))
        )

        assert len(results) == 5
        values = sorted([r.value for r in results])
        assert values == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_builder_multiple_stages(self):
        """Builder with multiple stages."""
        results = await (
            Pipeline.create()
            .add("Double", double, workers=2)
            .add("AddOne", add_one, workers=2)
            .add("ToString", to_string, workers=2)
            .run(list(range(3)))
        )

        assert len(results) == 3
        values = sorted([r.value for r in results])
        assert values == ["result_1", "result_3", "result_5"]

    @pytest.mark.asyncio
    async def test_builder_with_retries(self):
        """Builder respects retries parameter."""
        results = await (
            Pipeline.create()
            .add("Process", double, workers=2, retries=5)
            .run(list(range(3)))
        )

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_builder_build_returns_pipeline(self):
        """build() returns a Pipeline instance."""
        pipeline = (
            Pipeline.create()
            .add("Stage1", double, workers=2)
            .build()
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].name == "Stage1"

    @pytest.mark.asyncio
    async def test_builder_collect_results_false(self):
        """Builder respects collect_results setting."""
        pipeline = (
            Pipeline.create()
            .add("Stage1", double, workers=2)
            .collect_results(False)
            .build()
        )

        assert pipeline.collect_results is False


