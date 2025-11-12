"""
Basic AsyncExecutor example demonstrating submit, map, and as_completed.
"""

import asyncio

from antflow import AsyncExecutor


async def square(x: int) -> int:
    """Square a number with a small delay."""
    await asyncio.sleep(0.1)
    return x * x


async def cube(x: int) -> int:
    """Cube a number with a small delay."""
    await asyncio.sleep(0.15)
    return x * x * x


async def main():
    print("=== AsyncExecutor Basic Example ===\n")

    async with AsyncExecutor(max_workers=5) as executor:
        print("1. Using map():")
        results = []
        async for result in executor.map(square, range(10)):
            results.append(result)
        print(f"   Results: {results}\n")

        print("2. Using submit() for individual tasks:")
        futures = [executor.submit(cube, i) for i in range(5)]
        results = [await f.result() for f in futures]
        print(f"   Results: {results}\n")

        print("3. Using as_completed():")
        futures = [executor.submit(square, i) for i in range(5, 10)]
        async for future in executor.as_completed(futures):
            result = await future.result()
            print(f"   Completed: {result}")


if __name__ == "__main__":
    asyncio.run(main())
