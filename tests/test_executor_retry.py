from unittest.mock import Mock

import pytest
from tenacity import RetryError

from antflow import AsyncExecutor


class TestAsyncExecutorRetry:
    @pytest.mark.asyncio
    async def test_submit_retry_success(self):
        """Test submit retries and succeeds."""
        mock_func = Mock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), 42])

        async def task():
            return mock_func()

        async with AsyncExecutor(max_workers=1) as executor:
            future = executor.submit(task, retries=3, retry_delay=0.01)
            result = await future.result()

            assert result == 42
            assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_submit_retry_failure(self):
        """Test submit retries and fails after max retries."""
        mock_func = Mock(side_effect=ValueError("Always failing"))

        async def task():
            return mock_func()

        async with AsyncExecutor(max_workers=1) as executor:
            future = executor.submit(task, retries=2, retry_delay=0.01)

            with pytest.raises(RetryError):
                await future.result()

            assert mock_func.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_map_retry_success(self):
        """Test map retries and succeeds."""
        call_counts = {0: 0, 1: 0}

        async def task(x):
            call_counts[x] += 1
            if x == 0 and call_counts[x] < 2:
                raise ValueError("Fail once")
            return x * 2

        async with AsyncExecutor(max_workers=2) as executor:
            results = await executor.map(task, [0, 1], retries=2, retry_delay=0.01)

            assert results == [0, 2]
            assert call_counts[0] == 2
            assert call_counts[1] == 1

    @pytest.mark.asyncio
    async def test_map_retry_failure(self):
        """Test map retries and fails after max retries."""

        async def task(x):
            raise ValueError("Always failing")

        async with AsyncExecutor(max_workers=2) as executor:
            with pytest.raises(RetryError):
                await executor.map(task, [0], retries=2, retry_delay=0.01)

    @pytest.mark.asyncio
    async def test_map_iter_retry_success(self):
        """Test map_iter retries and succeeds."""
        call_counts = {0: 0, 1: 0}

        async def task(x):
            call_counts[x] += 1
            if x == 0 and call_counts[x] < 2:
                raise ValueError("Fail once")
            return x * 2

        async with AsyncExecutor(max_workers=2) as executor:
            results = []
            async for res in executor.map_iter(task, [0, 1], retries=2, retry_delay=0.01):
                results.append(res)

            assert results == [0, 2]
            assert call_counts[0] == 2
            assert call_counts[1] == 1

    @pytest.mark.asyncio
    async def test_map_iter_retry_failure(self):
        """Test map_iter retries and fails after max retries."""

        async def task(x):
            raise ValueError("Always failing")

        async with AsyncExecutor(max_workers=2) as executor:
            with pytest.raises(RetryError):
                async for _ in executor.map_iter(task, [0], retries=2, retry_delay=0.01):
                    pass
