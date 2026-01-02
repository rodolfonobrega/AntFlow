"""Tests for Pipeline.stream() async iterator."""

import asyncio

import pytest

from antflow import Pipeline, Stage


async def slow_double(x: int) -> int:
    await asyncio.sleep(0.05)
    return x * 2


async def fast_process(x: int) -> int:
    await asyncio.sleep(0.01)
    return x + 1


class TestPipelineStream:
    """Tests for Pipeline.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_results(self):
        """stream() yields results as they complete."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[slow_double])]
        )

        results = []
        async for result in pipeline.stream(list(range(5))):
            results.append(result.value)

        assert len(results) == 5
        assert sorted(results) == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_stream_early_exit(self):
        """stream() supports early exit with break."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=2, tasks=[slow_double])]
        )

        results = []
        async for result in pipeline.stream(list(range(10))):
            results.append(result.value)
            if len(results) >= 3:
                break

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_stream_completion_order(self):
        """stream() yields in completion order, not input order."""
        async def variable_delay(x: int) -> int:
            delay = 0.1 if x == 0 else 0.01
            await asyncio.sleep(delay)
            return x

        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=5, tasks=[variable_delay])]
        )

        results = []
        async for result in pipeline.stream(list(range(5))):
            results.append(result.value)

        assert len(results) == 5
        assert results[0] != 0 or results[-1] == 0

    @pytest.mark.asyncio
    async def test_stream_multi_stage(self):
        """stream() works with multi-stage pipelines."""
        pipeline = Pipeline(
            stages=[
                Stage(name="Double", workers=2, tasks=[slow_double]),
                Stage(name="AddOne", workers=2, tasks=[fast_process]),
            ]
        )

        results = []
        async for result in pipeline.stream(list(range(5))):
            results.append(result.value)

        assert len(results) == 5
        assert sorted(results) == [1, 3, 5, 7, 9]
