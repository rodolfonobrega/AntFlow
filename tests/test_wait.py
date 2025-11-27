"""
Tests for AsyncExecutor.wait() functionality.
"""

import asyncio

import pytest

from antflow import AsyncExecutor, WaitStrategy


@pytest.mark.asyncio
async def test_wait_all_completed():
    """Test waiting for all futures to complete."""
    async def task(x):
        await asyncio.sleep(0.01)
        return x * 2

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [executor.submit(task, i) for i in range(5)]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.ALL_COMPLETED
        )

        assert len(done) == 5
        assert len(pending) == 0

        results = [await f.result() for f in done]
        assert sorted(results) == [0, 2, 4, 6, 8]


@pytest.mark.asyncio
async def test_wait_first_completed():
    """Test waiting for first future to complete."""
    async def task_fast(x):
        await asyncio.sleep(0.01)
        return x

    async def task_slow(x):
        await asyncio.sleep(1.0)
        return x

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(task_fast, 1),
            executor.submit(task_slow, 2),
            executor.submit(task_slow, 3),
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_COMPLETED
        )

        assert len(done) == 1
        assert len(pending) == 2

        result = await list(done)[0].result()
        assert result == 1


@pytest.mark.asyncio
async def test_wait_first_exception():
    """Test waiting for first exception."""
    async def task_ok(x):
        await asyncio.sleep(0.01)
        return x

    async def task_fail(x):
        await asyncio.sleep(0.02)
        raise ValueError(f"Error for {x}")

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(task_ok, 1),
            executor.submit(task_fail, 2),
            executor.submit(task_ok, 3),
            executor.submit(task_ok, 4),
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_EXCEPTION
        )

        # Should return when first exception occurs
        assert len(done) >= 1
        assert len(pending) >= 0

        # Check that at least one future has an exception
        has_exception = any(f.exception() is not None for f in done)
        assert has_exception


@pytest.mark.asyncio
async def test_wait_timeout_all_completed():
    """Test timeout with ALL_COMPLETED strategy."""
    async def task(x):
        await asyncio.sleep(1.0)
        return x

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [executor.submit(task, i) for i in range(5)]

        with pytest.raises(asyncio.TimeoutError):
            await executor.wait(
                futures,
                timeout=0.1,
                return_when=WaitStrategy.ALL_COMPLETED
            )


@pytest.mark.asyncio
async def test_wait_timeout_first_completed():
    """Test timeout with FIRST_COMPLETED strategy (should not raise)."""
    async def task(x):
        await asyncio.sleep(1.0)
        return x

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [executor.submit(task, i) for i in range(5)]

        # Should not raise, just return empty done set
        done, pending = await executor.wait(
            futures,
            timeout=0.1,
            return_when=WaitStrategy.FIRST_COMPLETED
        )

        assert len(done) == 0
        assert len(pending) == 5


@pytest.mark.asyncio
async def test_wait_empty_futures():
    """Test wait with empty futures list."""
    async with AsyncExecutor(max_workers=5) as executor:
        done, pending = await executor.wait(
            [],
            return_when=WaitStrategy.ALL_COMPLETED
        )

        assert len(done) == 0
        assert len(pending) == 0


@pytest.mark.asyncio
async def test_wait_mixed_success_and_failure():
    """Test wait with mix of successful and failed futures."""
    async def task_ok(x):
        await asyncio.sleep(0.01)
        return x

    async def task_fail(x):
        await asyncio.sleep(0.01)
        raise RuntimeError(f"Failed {x}")

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(task_ok, 1),
            executor.submit(task_ok, 2),
            executor.submit(task_fail, 3),
            executor.submit(task_ok, 4),
            executor.submit(task_fail, 5),
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.ALL_COMPLETED
        )

        assert len(done) == 5
        assert len(pending) == 0

        # Count successes and failures
        successes = 0
        failures = 0

        for f in done:
            if f.exception() is None:
                successes += 1
            else:
                failures += 1

        assert successes == 3
        assert failures == 2


@pytest.mark.asyncio
async def test_wait_racing_tasks():
    """Test racing multiple tasks to get the fastest."""
    call_order = []

    async def task_a():
        await asyncio.sleep(0.05)
        call_order.append('A')
        return 'A'

    async def task_b():
        await asyncio.sleep(0.15)
        call_order.append('B')
        return 'B'

    async def task_c():
        await asyncio.sleep(0.25)
        call_order.append('C')
        return 'C'

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(task_a),
            executor.submit(task_b),
            executor.submit(task_c),
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_COMPLETED
        )

        assert len(done) == 1
        assert len(pending) == 2

        winner = list(done)[0]
        result = await winner.result()
        assert result == 'A'
        assert call_order[0] == 'A'


@pytest.mark.asyncio
async def test_wait_all_completed_with_timeout_success():
    """Test ALL_COMPLETED with timeout that doesn't expire."""
    async def task(x):
        await asyncio.sleep(0.01)
        return x * 2

    async with AsyncExecutor(max_workers=5) as executor:
        futures = [executor.submit(task, i) for i in range(3)]

        done, pending = await executor.wait(
            futures,
            timeout=5.0,  # Plenty of time
            return_when=WaitStrategy.ALL_COMPLETED
        )

        assert len(done) == 3
        assert len(pending) == 0
