"""Tests for Pipeline.stream() memory behavior."""

import asyncio
import pytest

from antflow import Pipeline, Stage


async def simple_task(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


class TestStreamMemory:
    """Tests for memory behavior of stream()."""

    @pytest.mark.asyncio
    async def test_stream_clears_results_after_use(self):
        """stream() should not leave results in _results."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[simple_task])], collect_results=True
        )

        original_collect = pipeline.collect_results
        assert original_collect is True

        # Run stream
        results_collected = []
        async for result in pipeline.stream(list(range(5))):
            results_collected.append(result.value)

        # Verify results were yielded
        assert len(results_collected) == 5
        assert sorted(results_collected) == [0, 2, 4, 6, 8]

        # Verify _results is empty after stream
        assert len(pipeline._results) == 0

        # Verify collect_results was restored
        assert pipeline.collect_results == original_collect

    @pytest.mark.asyncio
    async def test_stream_with_collect_results_false_initially(self):
        """stream() should work even when collect_results=False initially."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[simple_task])], collect_results=False
        )

        original_collect = pipeline.collect_results
        assert original_collect is False

        # Run stream
        results_collected = []
        async for result in pipeline.stream(list(range(3))):
            results_collected.append(result.value)

        # Verify results were yielded
        assert len(results_collected) == 3
        assert sorted(results_collected) == [0, 2, 4]

        # Verify _results is empty
        assert len(pipeline._results) == 0

        # Verify collect_results was restored
        assert pipeline.collect_results == original_collect

    @pytest.mark.asyncio
    async def test_run_preserves_collect_results_setting(self):
        """run() should respect the collect_results setting."""
        # Test with collect_results=False
        pipeline1 = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[simple_task])], collect_results=False
        )

        results1 = await pipeline1.run(list(range(3)))
        assert len(pipeline1._results) == 0
        assert len(results1) == 0

        # Test with collect_results=True (default)
        pipeline2 = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[simple_task])], collect_results=True
        )

        results2 = await pipeline2.run(list(range(3)))
        assert len(pipeline2._results) == 3
        assert len(results2) == 3
