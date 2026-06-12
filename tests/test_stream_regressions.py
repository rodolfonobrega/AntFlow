"""Regression tests for Pipeline.stream() and other robustness fixes."""

import asyncio
import functools
import pytest

from antflow import Pipeline, Stage, AsyncExecutor, PipelineResult


async def add_one(x: int) -> int:
    return x + 1


async def failing_task(x: int) -> int:
    if x == 2:
        raise ValueError("Intentional failure")
    return x * 2


class TestStreamRegressions:
    """Tests covering various edge cases and regression scenarios in streaming."""

    @pytest.mark.asyncio
    async def test_stream_with_failures_does_not_hang(self):
        """stream() should yield failed results with .error set and not hang."""
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[failing_task], task_attempts=1)
            ]
        )

        results = []
        async for res in pipeline.stream([1, 2, 3]):
            results.append(res)

        assert len(results) == 3
        # Sort by sequence ID to verify results
        sorted_res = sorted(results, key=lambda r: r.sequence_id)
        assert sorted_res[0].error is None
        assert sorted_res[0].value == 2
        assert sorted_res[1].error is not None
        assert isinstance(sorted_res[1].error, ValueError)
        assert "Intentional failure" in str(sorted_res[1].error)
        assert sorted_res[2].error is None
        assert sorted_res[2].value == 6

    @pytest.mark.asyncio
    async def test_stream_early_break_with_buffer_does_not_deadlock(self):
        """stream() with limited buffer and early break should exit without deadlock."""
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[add_one])
            ]
        )

        results = []
        gen = pipeline.stream(list(range(10)), buffer_size=1)
        try:
            async for res in gen:
                results.append(res)
                if len(results) == 2:
                    break
        finally:
            await gen.aclose()

        assert len(results) == 2
        # Clean shutdown check: make sure the runner task terminates
        await asyncio.sleep(0.1)
        assert pipeline._runner_task is None

    @pytest.mark.asyncio
    async def test_stream_early_break_does_not_leak_to_results(self):
        """stream() with early break should not leak results to pipeline.results."""
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[add_one])
            ]
        )

        results = []
        gen = pipeline.stream(list(range(10)), buffer_size=2)
        try:
            async for res in gen:
                results.append(res)
                if len(results) == 3:
                    break
        finally:
            await gen.aclose()

        # Let the workers finish background items
        await asyncio.sleep(0.5)

        assert len(results) == 3
        # Check that pipeline._results has not accumulated anything
        assert len(pipeline.results) == 0

    @pytest.mark.asyncio
    async def test_stream_buffer_size_zero_rendezvous(self):
        """buffer_size=0 should behave as a true rendezvous (zero-buffer) channel."""
        # We can verify it uses RendezvousChannel
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=1, tasks=[add_one])
            ]
        )

        results = []
        # Under the hood, buffer_size=0 should use RendezvousChannel
        async for res in pipeline.stream([1, 2, 3], buffer_size=0):
            results.append(res)

        assert len(results) == 3
        assert sorted([r.value for r in results]) == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_partial_function_as_task(self):
        """functools.partial tasks should validate and execute correctly."""
        async def async_add(x: int, y: int) -> int:
            return x + y

        # Create partial function wrapping the coroutine function
        partial_async_task = functools.partial(async_add, y=5)

        stage = Stage(
            name="PartialStage",
            workers=2,
            tasks=[partial_async_task]
        )

        pipeline = Pipeline(stages=[stage])
        results = await pipeline.run([1, 2, 3])

        assert len(results) == 3
        assert sorted([r.value for r in results]) == [6, 7, 8]

    @pytest.mark.asyncio
    async def test_executor_submit_without_context_manager(self):
        """AsyncExecutor.submit() should start workers and resolve futures without context manager."""
        executor = AsyncExecutor(max_workers=2)
        try:
            future = executor.submit(add_one, 10)
            result = await future.result(timeout=2.0)
            assert result == 11
        finally:
            await executor.shutdown()
