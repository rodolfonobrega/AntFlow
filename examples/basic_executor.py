"""
Basic AsyncExecutor example demonstrating submit, map, map_iter, and as_completed.
"""

import asyncio
import time

from antflow import AsyncExecutor


async def square(x: int) -> int:
    """Square a number with a small delay."""
    await asyncio.sleep(0.1)
    return x * x


async def cube(x: int) -> int:
    """Cube a number with a small delay."""
    await asyncio.sleep(0.15)
    return x * x * x


async def variable_delay_task(x: int) -> str:
    """Task where item 0 is slow, others are fast."""
    delay = 1.5 if x == 0 else 0.2
    await asyncio.sleep(delay)
    return f"Result-{x}"


async def main():
    print("=== AsyncExecutor Basic Example ===\n")

    async with AsyncExecutor(max_workers=5) as executor:
        print("1. Using map() - returns list directly:")
        results = await executor.map(square, range(10))
        print(f"   Results: {results}\n")

        print("2. Using map_iter() - streaming with async for:")
        results = []
        async for result in executor.map_iter(square, range(10)):
            results.append(result)
        print(f"   Results: {results}\n")

        print("3. Using submit() for individual tasks:")
        futures = [executor.submit(cube, i) for i in range(5)]
        results = [await f.result() for f in futures]
        print(f"   Results: {results}\n")

        print("4. Using as_completed() - results as they finish:")
        futures = [executor.submit(square, i) for i in range(5, 10)]
        async for future in executor.as_completed(futures):
            result = await future.result()
            print(f"   Completed: {result}")

    print("\n" + "=" * 50)
    print("=== map() vs as_completed() Comparison ===")
    print("=" * 50)
    print("\nItem 0 takes 1.5s, items 1-4 take 0.2s each.\n")

    async with AsyncExecutor(max_workers=5) as executor:
        print("map() - waits for INPUT order:")
        start = time.time()
        results = await executor.map(variable_delay_task, range(5))
        elapsed = time.time() - start
        for r in results:
            print(f"   {r}")
        print(f"   (all returned after {elapsed:.1f}s)\n")

        print("as_completed() - returns in COMPLETION order:")
        start = time.time()
        futures = [executor.submit(variable_delay_task, i) for i in range(5)]
        async for future in executor.as_completed(futures):
            result = await future.result()
            elapsed = time.time() - start
            print(f"   {result} (at {elapsed:.1f}s)")


if __name__ == "__main__":
    asyncio.run(main())
