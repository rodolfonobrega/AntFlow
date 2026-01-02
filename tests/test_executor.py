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
    async def test_map_returns_list(self):
        """Test map returns list directly."""
        async with AsyncExecutor(max_workers=3) as executor:
            results = await executor.map(simple_task, range(10))
            assert results == [i * 2 for i in range(10)]

    @pytest.mark.asyncio
    async def test_map_with_retries(self):
        """Test map with retry parameters."""
        call_counts = {}

        async def flaky_task(x: int) -> int:
            call_counts[x] = call_counts.get(x, 0) + 1
            if x == 0 and call_counts[x] < 2:
                raise ValueError("Temporary failure")
            await asyncio.sleep(0.01)
            return x * 2

        async with AsyncExecutor(max_workers=3) as executor:
            results = await executor.map(
                flaky_task, range(5), retries=2, retry_delay=0.01
            )
            assert results == [i * 2 for i in range(5)]
            assert call_counts[0] == 2

    @pytest.mark.asyncio
    async def test_map_multiple_iterables(self):
        """Test map with multiple iterables."""
        async def add(x: int, y: int) -> int:
            await asyncio.sleep(0.01)
            return x + y

        async with AsyncExecutor(max_workers=3) as executor:
            results = await executor.map(add, [1, 2, 3], [10, 20, 30])
            assert results == [11, 22, 33]

    @pytest.mark.asyncio
    async def test_map_empty_iterable(self):
        """Test map with empty iterable."""
        async with AsyncExecutor(max_workers=3) as executor:
            results = await executor.map(simple_task, [])
            assert results == []

    @pytest.mark.asyncio
    async def test_map_exception_propagated(self):
        """Test map propagates exceptions when no retries."""
        async with AsyncExecutor(max_workers=2) as executor:
            with pytest.raises(ValueError, match="Task failed for 1"):
                await executor.map(failing_task, [1, 2, 3])

    @pytest.mark.asyncio
    async def test_map_on_shutdown_executor(self):
        """Test map raises error on shutdown executor."""
        executor = AsyncExecutor(max_workers=2)
        await executor.shutdown()

        with pytest.raises(ExecutorShutdownError):
            await executor.map(simple_task, range(5))

    @pytest.mark.asyncio
    async def test_map_preserves_order(self):
        """Test map preserves input order even with varying task times."""
        async def variable_delay_task(x: int) -> int:
            delay = 0.1 if x % 2 == 0 else 0.01
            await asyncio.sleep(delay)
            return x

        async with AsyncExecutor(max_workers=5) as executor:
            results = await executor.map(variable_delay_task, range(10))
            assert results == list(range(10))

    @pytest.mark.asyncio
    async def test_map_iter_streaming(self):
        """Test map_iter yields results as async iterator."""
        async with AsyncExecutor(max_workers=3) as executor:
            results = []
            async for result in executor.map_iter(simple_task, range(10)):
                results.append(result)
            assert results == [i * 2 for i in range(10)]

    @pytest.mark.asyncio
    async def test_map_iter_early_exit(self):
        """Test map_iter allows early exit."""
        processed = []

        async def tracking_task(x: int) -> int:
            processed.append(x)
            await asyncio.sleep(0.01)
            return x * 2

        async with AsyncExecutor(max_workers=3) as executor:
            results = []
            async for result in executor.map_iter(tracking_task, range(10)):
                results.append(result)
                if len(results) >= 3:
                    break
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_map_iter_with_retries(self):
        """Test map_iter with retry parameters."""
        call_counts = {}

        async def flaky_task(x: int) -> int:
            call_counts[x] = call_counts.get(x, 0) + 1
            if x == 0 and call_counts[x] < 2:
                raise ValueError("Temporary failure")
            await asyncio.sleep(0.01)
            return x * 2

        async with AsyncExecutor(max_workers=3) as executor:
            results = []
            async for result in executor.map_iter(
                flaky_task, range(5), retries=2, retry_delay=0.01
            ):
                results.append(result)
            assert results == [i * 2 for i in range(5)]
            assert call_counts[0] == 2

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
