"""Tests for AsyncExecutor."""

import asyncio

import pytest

from antflow import AsyncExecutor, ExecutorShutdownError


async def simple_task(x: int) -> int:
    """Simple test task."""
    await asyncio.sleep(0.01)
    return x * 2


async def failing_task(x: int) -> int:
    """Task that always fails."""
    await asyncio.sleep(0.01)
    raise ValueError(f"Task failed for {x}")


class TestAsyncExecutor:
    """Test cases for AsyncExecutor."""

    @pytest.mark.asyncio
    async def test_submit_single_task(self):
        """Test submitting a single task."""
        async with AsyncExecutor(max_workers=2) as executor:
            future = executor.submit(simple_task, 5)
            result = await future.result()
            assert result == 10

    @pytest.mark.asyncio
    async def test_submit_multiple_tasks(self):
        """Test submitting multiple tasks."""
        async with AsyncExecutor(max_workers=3) as executor:
            futures = [executor.submit(simple_task, i) for i in range(10)]
            results = [await f.result() for f in futures]
            assert results == [i * 2 for i in range(10)]

    @pytest.mark.asyncio
    async def test_map_ordered(self):
        """Test map with order preservation."""
        async with AsyncExecutor(max_workers=3) as executor:
            results = []
            async for result in executor.map(simple_task, range(10)):
                results.append(result)
            assert results == [i * 2 for i in range(10)]

    @pytest.mark.asyncio
    async def test_as_completed(self):
        """Test as_completed method."""
        async with AsyncExecutor(max_workers=3) as executor:
            futures = [executor.submit(simple_task, i) for i in range(5)]

            results = []
            async for future in executor.as_completed(futures):
                result = await future.result()
                results.append(result)

            assert sorted(results) == [i * 2 for i in range(5)]

    @pytest.mark.asyncio
    async def test_task_exception(self):
        """Test that task exceptions are properly propagated."""
        async with AsyncExecutor(max_workers=2) as executor:
            future = executor.submit(failing_task, 1)

            with pytest.raises(ValueError, match="Task failed for 1"):
                await future.result()

    @pytest.mark.asyncio
    async def test_shutdown_prevents_new_tasks(self):
        """Test that shutdown prevents submitting new tasks."""
        executor = AsyncExecutor(max_workers=2)
        await executor.shutdown()

        with pytest.raises(ExecutorShutdownError):
            executor.submit(simple_task, 1)

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager functionality."""
        executor = AsyncExecutor(max_workers=2)

        async with executor:
            future = executor.submit(simple_task, 5)
            result = await future.result()
            assert result == 10

        with pytest.raises(ExecutorShutdownError):
            executor.submit(simple_task, 1)

    @pytest.mark.asyncio
    async def test_future_done(self):
        """Test future done() method."""
        async with AsyncExecutor(max_workers=2) as executor:
            future = executor.submit(simple_task, 5)
            assert not future.done()

            await future.result()
            assert future.done()

    @pytest.mark.asyncio
    async def test_future_exception(self):
        """Test future exception() method."""
        async with AsyncExecutor(max_workers=2) as executor:
            future = executor.submit(failing_task, 1)

            try:
                await future.result()
            except ValueError:
                pass

            assert future.exception() is not None
            assert isinstance(future.exception(), ValueError)

    @pytest.mark.asyncio
    async def test_max_workers_validation(self):
        """Test that max_workers must be at least 1."""
        with pytest.raises(ValueError, match="max_workers must be at least 1"):
            AsyncExecutor(max_workers=0)
