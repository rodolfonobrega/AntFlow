"""
Example demonstrating the wait() function with different strategies.
"""

import asyncio
import random

from antflow import AsyncExecutor, WaitStrategy


async def task_quick(x: int) -> int:
    """A quick task that completes in 0.1 seconds."""
    await asyncio.sleep(0.1)
    return x * 2


async def task_slow(x: int) -> int:
    """A slower task that takes 1 second."""
    await asyncio.sleep(1.0)
    return x * 3


async def task_random(x: int) -> int:
    """A task with random duration."""
    await asyncio.sleep(random.uniform(0.1, 0.5))
    return x * 10


async def task_failing(x: int) -> int:
    """A task that sometimes fails."""
    await asyncio.sleep(0.2)
    if x == 5:
        raise ValueError(f"Simulated error for {x}")
    return x * 5


async def main():
    print("=" * 60)
    print("AsyncExecutor.wait() Examples")
    print("=" * 60)
    print()

    async with AsyncExecutor(max_workers=10) as executor:
        # Example 1: Wait for ALL to complete
        print("1. Wait for ALL futures to complete:")
        futures = [executor.submit(task_random, i) for i in range(5)]

        done, pending = await executor.wait(futures, return_when=WaitStrategy.ALL_COMPLETED)

        print(f"   All {len(done)} futures completed")
        results = [await f.result() for f in done]
        print(f"   Results: {results}")
        print()

        # Example 2: Wait for FIRST to complete
        print("2. Wait for FIRST future to complete:")
        futures = [
            executor.submit(task_quick, 1),
            executor.submit(task_slow, 2),
            executor.submit(task_slow, 3),
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_COMPLETED
        )

        print(f"   {len(done)} future(s) completed, {len(pending)} still pending")
        for f in done:
            result = await f.result()
            print(f"   First result: {result}")
        print()

        # Example 3: Wait for FIRST_EXCEPTION
        print("3. Wait for FIRST exception:")
        futures = [
            executor.submit(task_failing, i) for i in range(10)
        ]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_EXCEPTION
        )

        print(f"   {len(done)} future(s) completed, {len(pending)} still pending")

        # Check for exceptions
        for f in done:
            try:
                result = await f.result()
                print(f"   Success: {result}")
            except Exception as e:
                print(f"   Exception found: {e}")
                break
        print()

        # Example 4: Wait with timeout
        print("4. Wait with timeout (2 seconds):")
        futures = [
            executor.submit(task_slow, i) for i in range(5)
        ]

        try:
            done, pending = await executor.wait(
                futures,
                timeout=2.0,
                return_when=WaitStrategy.ALL_COMPLETED
            )
            print("   All completed within timeout")
        except asyncio.TimeoutError:
            print("   Timeout! Some futures still pending")
        print()

        # Example 5: Practical use case - process until first error
        print("5. Practical: Process until first error occurs:")

        async def risky_task(x: int) -> int:
            await asyncio.sleep(random.uniform(0.1, 0.3))
            if random.random() < 0.3:  # 30% chance of failure
                raise RuntimeError(f"Task {x} failed")
            return x * 100

        futures = [executor.submit(risky_task, i) for i in range(20)]

        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_EXCEPTION
        )

        # Process results
        successes = []
        errors = []

        for f in done:
            try:
                result = await f.result()
                successes.append(result)
            except Exception as e:
                errors.append(e)

        print(f"   Processed {len(done)} tasks before error")
        print(f"   Successes: {len(successes)}")
        print(f"   Errors: {len(errors)}")
        print(f"   Still pending: {len(pending)}")

        if errors:
            print(f"   First error: {errors[0]}")
        print()

        # Example 6: Racing multiple tasks
        print("6. Racing tasks - get the fastest result:")

        async def api_call_region_1(query: str) -> str:
            await asyncio.sleep(random.uniform(0.1, 0.5))
            return f"Region 1 result for '{query}'"

        async def api_call_region_2(query: str) -> str:
            await asyncio.sleep(random.uniform(0.1, 0.5))
            return f"Region 2 result for '{query}'"

        async def api_call_region_3(query: str) -> str:
            await asyncio.sleep(random.uniform(0.1, 0.5))
            return f"Region 3 result for '{query}'"

        # Submit the same query to multiple regions
        query = "important data"
        futures = [
            executor.submit(api_call_region_1, query),
            executor.submit(api_call_region_2, query),
            executor.submit(api_call_region_3, query),
        ]

        # Get the first result
        done, pending = await executor.wait(
            futures,
            return_when=WaitStrategy.FIRST_COMPLETED
        )

        fastest = list(done)[0]
        result = await fastest.result()

        print(f"   Fastest response: {result}")
        print(f"   Got result while {len(pending)} requests still pending")
        print()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    random.seed(42)  # For reproducible results in examples
    asyncio.run(main())
