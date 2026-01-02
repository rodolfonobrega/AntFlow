"""
Streaming Results example demonstrating Pipeline.stream() async iterator.

stream() yields results as they complete, allowing:
- Processing results before pipeline finishes
- Early exit when a condition is met
- Memory-efficient processing of large datasets
"""

import asyncio
import random

from antflow import Pipeline, Stage


async def variable_delay_task(item_id: int) -> dict:
    """Task with variable delay - some items complete faster than others."""
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)
    return {"id": item_id, "delay": delay}


async def process_item(item: dict) -> dict:
    """Process the item."""
    await asyncio.sleep(random.uniform(0.05, 0.1))
    item["processed"] = True
    return item


async def main():
    print("=" * 60)
    print("Pipeline.stream() Examples")
    print("=" * 60)

    print("\n1. Basic streaming - results as they complete:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[Stage(name="Process", workers=5, tasks=[variable_delay_task])]
    )

    results_order = []
    async for result in pipeline.stream(list(range(10))):
        results_order.append(result.value["id"])
        print(f"   Got result {result.value['id']} (delay: {result.value['delay']:.2f}s)")

    print(f"   Completion order: {results_order}")
    print(f"   Note: Order differs from input [0,1,2,...] due to variable delays")

    print("\n2. Early exit - stop when condition met:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[Stage(name="Process", workers=5, tasks=[variable_delay_task])]
    )

    count = 0
    target = 5
    async for result in pipeline.stream(list(range(20))):
        count += 1
        print(f"   Processing result {count}: item {result.value['id']}")
        if count >= target:
            print(f"   Reached target of {target} results, exiting early!")
            break

    print(f"   Only processed {count} of 20 items")

    print("\n3. Find first matching result:")
    print("-" * 40)

    async def search_task(x: int) -> dict:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        return {"id": x, "is_target": x == 7}

    pipeline = Pipeline(
        stages=[Stage(name="Search", workers=5, tasks=[search_task])]
    )

    found = None
    async for result in pipeline.stream(list(range(20))):
        if result.value["is_target"]:
            found = result.value["id"]
            print(f"   Found target: {found}")
            break

    if found is None:
        print("   Target not found")

    print("\n4. Multi-stage streaming:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=3, tasks=[variable_delay_task]),
            Stage(name="Process", workers=3, tasks=[process_item]),
        ]
    )

    count = 0
    async for result in pipeline.stream(list(range(10))):
        count += 1
        item = result.value
        print(f"   Item {item['id']}: processed={item['processed']}")

    print(f"   Total streamed: {count}")

    print("\n5. Aggregating streamed results:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[Stage(name="Generate", workers=5, tasks=[variable_delay_task])]
    )

    total_delay = 0.0
    count = 0
    async for result in pipeline.stream(list(range(15))):
        total_delay += result.value["delay"]
        count += 1

    avg_delay = total_delay / count
    print(f"   Processed {count} items")
    print(f"   Total delay time: {total_delay:.2f}s")
    print(f"   Average delay: {avg_delay:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
