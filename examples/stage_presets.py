"""
Stage Presets example demonstrating io_bound(), cpu_bound(), and rate_limited().

Presets provide pre-configured stages for common patterns:
- io_bound: High workers (10), 3 retries - for API calls, file I/O
- cpu_bound: Workers = CPU count, 1 retry - for computation
- rate_limited: Enforces RPS limit - for rate-limited APIs
"""

import asyncio
import os
import random

from antflow import Pipeline, Stage


async def fetch_from_api(item_id: int) -> dict:
    """Simulate fetching from an external API."""
    await asyncio.sleep(random.uniform(0.05, 0.15))
    return {"id": item_id, "data": f"api_response_{item_id}"}


async def cpu_intensive_transform(item: dict) -> dict:
    """Simulate CPU-intensive data transformation."""
    await asyncio.sleep(random.uniform(0.02, 0.05))
    item["processed"] = sum(ord(c) for c in str(item["data"]))
    return item


async def call_rate_limited_api(item: dict) -> dict:
    """Simulate calling a rate-limited external API."""
    await asyncio.sleep(0.1)
    item["enriched"] = True
    return item


async def save_to_database(item: dict) -> str:
    """Simulate saving to database."""
    await asyncio.sleep(random.uniform(0.02, 0.08))
    return f"saved_{item['id']}"


async def main():
    print("=" * 60)
    print("Stage Presets Examples")
    print("=" * 60)

    items = list(range(30))

    print("\n1. I/O Bound preset (default: 10 workers, 3 retries):")
    print("-" * 40)
    io_stage = Stage.io_bound("Fetch", fetch_from_api)
    print(f"   Workers: {io_stage.workers}")
    print(f"   Retries: {io_stage.task_attempts}")

    print("\n2. CPU Bound preset (default: CPU count workers, 1 retry):")
    print("-" * 40)
    cpu_stage = Stage.cpu_bound("Transform", cpu_intensive_transform)
    print(f"   Workers: {cpu_stage.workers} (CPU count: {os.cpu_count()})")
    print(f"   Retries: {cpu_stage.task_attempts}")

    print("\n3. Rate Limited preset (enforces RPS):")
    print("-" * 40)
    rate_stage = Stage.rate_limited("API", call_rate_limited_api, rps=5)
    print(f"   Workers: {rate_stage.workers}")
    print(f"   Concurrency limits: {rate_stage.task_concurrency_limits}")

    print("\n4. Custom preset parameters:")
    print("-" * 40)
    custom_io = Stage.io_bound("FastFetch", fetch_from_api, workers=20, retries=5)
    custom_cpu = Stage.cpu_bound("HeavyProcess", cpu_intensive_transform, workers=4, retries=2)
    custom_rate = Stage.rate_limited("SlowAPI", call_rate_limited_api, rps=2, retries=5)
    print(f"   Custom I/O: {custom_io.workers} workers, {custom_io.task_attempts} retries")
    print(f"   Custom CPU: {custom_cpu.workers} workers, {custom_cpu.task_attempts} retries")
    print(f"   Custom Rate: {custom_rate.workers} workers, RPS={custom_rate.task_concurrency_limits}")

    print("\n5. Full pipeline with presets:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[
            Stage.io_bound("Fetch", fetch_from_api, workers=5),
            Stage.cpu_bound("Transform", cpu_intensive_transform),
            Stage.rate_limited("Enrich", call_rate_limited_api, rps=3),
            Stage.io_bound("Save", save_to_database, workers=3),
        ]
    )

    print("   Pipeline stages:")
    for stage in pipeline.stages:
        limits = stage.task_concurrency_limits
        limit_str = f", limits={limits}" if limits else ""
        print(f"     {stage.name}: {stage.workers} workers, {stage.task_attempts} retries{limit_str}")

    print("\n   Running pipeline with progress...")
    results = await pipeline.run(items, progress=True)
    print(f"   Processed: {len(results)} items")

    print("\n6. Compare execution times:")
    print("-" * 40)

    async def measure_pipeline(stages, items):
        pipeline = Pipeline(stages=stages)
        start = asyncio.get_event_loop().time()
        await pipeline.run(items)
        return asyncio.get_event_loop().time() - start

    test_items = list(range(20))

    time_low_workers = await measure_pipeline(
        [Stage.io_bound("Fetch", fetch_from_api, workers=2)],
        test_items,
    )

    time_high_workers = await measure_pipeline(
        [Stage.io_bound("Fetch", fetch_from_api, workers=10)],
        test_items,
    )

    print(f"   2 workers: {time_low_workers:.2f}s")
    print(f"   10 workers: {time_high_workers:.2f}s")
    print(f"   Speedup: {time_low_workers / time_high_workers:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())
