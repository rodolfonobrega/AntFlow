"""
Builder Pattern example demonstrating Pipeline.create() fluent API.

The builder pattern provides a chainable API for constructing pipelines
with full control over stages, workers, and options.
"""

import asyncio
import random

from antflow import Pipeline, StatusTracker


async def fetch(item_id: int) -> dict:
    """Fetch data from source."""
    await asyncio.sleep(random.uniform(0.05, 0.1))
    return {"id": item_id, "raw": f"raw_data_{item_id}"}


async def validate(item: dict) -> dict:
    """Validate the fetched data."""
    await asyncio.sleep(random.uniform(0.02, 0.05))
    item["valid"] = True
    return item


async def transform(item: dict) -> dict:
    """Transform the data."""
    await asyncio.sleep(random.uniform(0.03, 0.08))
    item["transformed"] = item["raw"].upper()
    return item


async def enrich(item: dict) -> dict:
    """Enrich with additional data."""
    await asyncio.sleep(random.uniform(0.02, 0.05))
    item["enriched"] = True
    item["timestamp"] = asyncio.get_event_loop().time()
    return item


async def save(item: dict) -> str:
    """Save to destination."""
    await asyncio.sleep(random.uniform(0.02, 0.06))
    return f"saved_{item['id']}"


async def main():
    print("=" * 60)
    print("Pipeline Builder Pattern Examples")
    print("=" * 60)

    items = list(range(30))

    print("\n1. Basic builder usage:")
    print("-" * 40)
    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=5)
        .add("Process", transform, workers=3)
        .add("Save", save, workers=2)
        .run(items, progress=True)
    )
    print(f"   Processed: {len(results)} items")

    print("\n2. Multiple tasks per stage:")
    print("-" * 40)
    results = await (
        Pipeline.create()
        .add("Fetch", fetch, validate, workers=5)
        .add("Transform", transform, enrich, workers=3)
        .add("Save", save, workers=2)
        .run(items, progress=True)
    )
    print(f"   Processed: {len(results)} items")

    print("\n3. With status tracker:")
    print("-" * 40)
    tracker = StatusTracker()
    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=5)
        .add("Transform", transform, workers=3)
        .with_tracker(tracker)
        .run(items, progress=True)
    )
    stats = tracker.get_stats()
    print(f"   Completed: {stats['completed']}")
    print(f"   Failed: {stats['failed']}")

    print("\n4. Build pipeline separately:")
    print("-" * 40)
    pipeline = (
        Pipeline.create()
        .add("Fetch", fetch, workers=5, retries=3)
        .add("Process", transform, workers=3, retries=2)
        .add("Save", save, workers=2, retries=3)
        .build()
    )

    print(f"   Stages: {[s.name for s in pipeline.stages]}")
    print(f"   Total workers: {sum(s.workers for s in pipeline.stages)}")

    results = await pipeline.run(items, dashboard="compact")
    print(f"   Processed: {len(results)} items")

    print("\n5. Disable result collection (fire-and-forget):")
    print("-" * 40)
    pipeline = (
        Pipeline.create()
        .add("Process", transform, workers=3)
        .collect_results(False)
        .build()
    )
    results = await pipeline.run(items[:5])
    print(f"   Results collected: {len(results)} (expected 0)")


if __name__ == "__main__":
    asyncio.run(main())
