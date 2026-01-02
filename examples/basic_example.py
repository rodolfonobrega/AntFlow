"""
Basic AntFlow Examples - Two Ways to Create Pipelines

AntFlow offers two equivalent ways to define pipelines:

1. Using Stage objects (explicit, full control)
2. Using Pipeline.create().add() (fluent, concise)

Both produce the same result - choose based on your preference.
"""

import asyncio
import random

from antflow import Pipeline, Stage


async def fetch(item_id: int) -> dict:
    """Simulate fetching data from an API."""
    await asyncio.sleep(random.uniform(0.05, 0.15))
    return {"id": item_id, "data": f"data_{item_id}"}


async def process(item: dict) -> dict:
    """Simulate processing the data."""
    await asyncio.sleep(random.uniform(0.03, 0.1))
    item["processed"] = True
    item["data"] = item["data"].upper()
    return item


async def save(item: dict) -> str:
    """Simulate saving to database."""
    await asyncio.sleep(random.uniform(0.02, 0.08))
    return f"saved_{item['id']}"


async def main():
    print("=" * 70)
    print("AntFlow Basic Examples - Two Ways to Create Pipelines")
    print("=" * 70)

    items = list(range(20))

    # =========================================================================
    # METHOD 1: Using Stage objects (explicit, full control)
    # =========================================================================
    print("\n" + "=" * 70)
    print("METHOD 1: Using Stage objects")
    print("=" * 70)
    print("""
    Use this when you need:
    - Fine-grained control over each stage
    - Different retry strategies per stage
    - Task concurrency limits
    - Custom callbacks (on_success, on_failure)
    """)

    print("Example 1a: Single stage pipeline")
    print("-" * 40)

    stage = Stage(
        name="Fetch",
        workers=5,
        tasks=[fetch],
    )
    pipeline = Pipeline(stages=[stage])
    results = await pipeline.run(items, progress=True)
    print(f"   Results: {len(results)} items\n")

    print("Example 1b: Multi-stage pipeline")
    print("-" * 40)

    fetch_stage = Stage(
        name="Fetch",
        workers=5,
        tasks=[fetch],
        retry="per_task",
        task_attempts=3,
    )
    process_stage = Stage(
        name="Process",
        workers=3,
        tasks=[process],
    )
    save_stage = Stage(
        name="Save",
        workers=2,
        tasks=[save],
        retry="per_task",
        task_attempts=2,
    )

    pipeline = Pipeline(stages=[fetch_stage, process_stage, save_stage])
    results = await pipeline.run(items, progress=True)
    print(f"   Results: {len(results)} items")
    print(f"   Sample: {results[0].value}\n")

    # =========================================================================
    # METHOD 2: Using Pipeline.create().add() (fluent, concise)
    # =========================================================================
    print("\n" + "=" * 70)
    print("METHOD 2: Using Pipeline.create().add() - Fluent API")
    print("=" * 70)
    print("""
    Use this when you want:
    - Concise, readable pipeline definitions
    - Quick prototyping
    - Chainable configuration
    """)

    print("Example 2a: Single stage pipeline")
    print("-" * 40)

    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=5)
        .run(items, progress=True)
    )
    print(f"   Results: {len(results)} items\n")

    print("Example 2b: Multi-stage pipeline")
    print("-" * 40)

    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=5, retries=3)
        .add("Process", process, workers=3)
        .add("Save", save, workers=2, retries=2)
        .run(items, progress=True)
    )
    print(f"   Results: {len(results)} items")
    print(f"   Sample: {results[0].value}\n")

    print("Example 2c: Multiple tasks in one stage")
    print("-" * 40)

    results = await (
        Pipeline.create()
        .add("FetchAndProcess", fetch, process, workers=5)
        .add("Save", save, workers=2)
        .run(items, progress=True)
    )
    print(f"   Results: {len(results)} items\n")

    # =========================================================================
    # METHOD 3: Pipeline.quick() - One-liner for simple cases
    # =========================================================================
    print("\n" + "=" * 70)
    print("METHOD 3: Pipeline.quick() - One-liner for simple cases")
    print("=" * 70)
    print("""
    Use this for:
    - Quick scripts
    - Simple transformations
    - When you don't need multi-stage pipelines
    """)

    print("Example 3a: Single task")
    print("-" * 40)

    results = await Pipeline.quick(items, fetch, workers=5, progress=True)
    print(f"   Results: {len(results)} items\n")

    print("Example 3b: Multiple tasks (creates one stage per task)")
    print("-" * 40)

    results = await Pipeline.quick(
        items,
        [fetch, process, save],
        workers=5,
        progress=True,
    )
    print(f"   Results: {len(results)} items\n")

    # =========================================================================
    # COMPARISON: All three methods produce the same result
    # =========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON: All methods are equivalent")
    print("=" * 70)

    print("""
    # Method 1: Stage objects
    stage = Stage(name="Process", workers=5, tasks=[my_task])
    pipeline = Pipeline(stages=[stage])
    results = await pipeline.run(items)

    # Method 2: Fluent API
    results = await (
        Pipeline.create()
        .add("Process", my_task, workers=5)
        .run(items)
    )

    # Method 3: Quick one-liner
    results = await Pipeline.quick(items, my_task, workers=5)
    """)

    # =========================================================================
    # DISPLAY OPTIONS: progress bar and dashboards
    # =========================================================================
    print("\n" + "=" * 70)
    print("DISPLAY OPTIONS: Progress bars and dashboards")
    print("=" * 70)
    print("""
    All display options are OPTIONAL. By default, pipelines run silently.

    | Option                      | What it shows                          |
    |-----------------------------|----------------------------------------|
    | (nothing)                   | Silent - no output                     |
    | progress=True               | Simple bar - overall progress only     |
    | dashboard="compact"         | Single panel + current stage activity  |
    | dashboard="detailed"        | Per-stage progress table               |
    | dashboard="full"            | Everything + worker states + errors    |
    | custom_dashboard=MyClass()  | Your own implementation                |

    IMPORTANT:
    - progress=True shows END-TO-END progress (items that finished ALL stages)
    - For PER-STAGE progress, use dashboard="detailed" or "full"
    """)

    print("Option 1: No display (silent) - just returns results:")
    print("-" * 40)
    results = await Pipeline.quick(items, fetch, workers=5)
    print(f"   Completed silently: {len(results)} items\n")

    print("Option 2: Simple progress bar (progress=True):")
    print("-" * 40)
    print("   Shows overall progress - items that completed ALL stages")
    results = await Pipeline.quick(items, fetch, workers=5, progress=True)

    print("\nOption 3: Compact dashboard (dashboard='compact'):")
    print("-" * 40)
    print("   Shows overall progress + which stages are currently active")
    results = await Pipeline.quick(items, fetch, workers=5, dashboard="compact")

    print("\nOption 4: Detailed dashboard (dashboard='detailed'):")
    print("-" * 40)
    print("   Shows PER-STAGE progress table - see each stage individually")
    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=5)
        .add("Process", process, workers=3)
        .run(items, dashboard="detailed")
    )

    print("\n" + "=" * 70)
    print("Done! See other examples for advanced features.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
