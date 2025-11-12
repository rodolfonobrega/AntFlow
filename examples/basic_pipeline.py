"""
Basic Pipeline example with two stages.
"""

import asyncio

from antflow import Pipeline, Stage


async def extract(x: int) -> str:
    """Extract/fetch data."""
    await asyncio.sleep(0.05)
    return f"data_{x}"


async def transform(x: str) -> str:
    """Transform data."""
    await asyncio.sleep(0.05)
    return x.upper()


async def load(x: str) -> str:
    """Load/save data."""
    await asyncio.sleep(0.05)
    return f"saved_{x}"


async def main():
    print("=== Basic Pipeline Example ===\n")

    extract_stage = Stage(
        name="Extract",
        workers=3,
        tasks=[extract],
        retry="per_task",
        task_attempts=3
    )

    transform_stage = Stage(
        name="Transform",
        workers=2,
        tasks=[transform, load],
        retry="per_task",
        task_attempts=3
    )

    pipeline = Pipeline(
        stages=[extract_stage, transform_stage],
        collect_results=True
    )

    print(f"Pipeline stages: {[s.name for s in pipeline.stages]}")
    print(f"Total workers: {sum(s.workers for s in pipeline.stages)}\n")

    items = list(range(20))
    print(f"Processing {len(items)} items through pipeline...\n")

    results = await pipeline.run(items)

    print(f"\n✅ Completed! Processed {len(results)} items")
    print("\nFirst 5 results:")
    for result in results[:5]:
        print(f"  ID {result['id']}: {result['value']}")

    print(f"\nPipeline stats: {pipeline.get_stats()}")


if __name__ == "__main__":
    asyncio.run(main())
