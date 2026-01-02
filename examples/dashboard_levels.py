"""
Dashboard Levels example demonstrating different visualization options.

AntFlow provides OPTIONAL display options. By default, pipelines run silently.

DISPLAY OPTIONS:
----------------
| Option                      | What it shows                              |
|-----------------------------|-----------------------------------------------|
| (nothing)                   | Silent - no output, just returns results      |
| progress=True               | Simple bar - overall END-TO-END progress only |
| dashboard="compact"         | Single panel + current stage activity         |
| dashboard="detailed"        | PER-STAGE progress table (recommended)        |
| dashboard="full"            | Everything + worker states + error log        |
| custom_dashboard=MyClass()  | Your own implementation                       |

IMPORTANT:
- progress=True shows END-TO-END progress (items that finished ALL stages)
- For PER-STAGE progress visibility, use dashboard="detailed" or "full"
- For multi-stage pipelines, "detailed" is recommended to see bottlenecks

Example output of dashboard="detailed":
    ╭─────────────── Stage Status ───────────────╮
    │ Stage    │ Workers │ Pending │ Done │ Fail │
    │ Fetch    │   3/5   │    15   │  82  │   0  │
    │ Process  │   2/3   │    32   │  48  │   2  │
    │ Save     │   1/2   │    18   │  15  │   0  │
    ╰────────────────────────────────────────────╯
"""

import asyncio
import random

from antflow import Pipeline, Stage, StatusTracker


async def fetch_data(item_id: int) -> dict:
    """Simulate fetching data with random delays."""
    await asyncio.sleep(random.uniform(0.1, 0.3))
    if random.random() < 0.1:
        raise ValueError("Connection timeout")
    return {"id": item_id, "data": f"data_{item_id}"}


async def process_data(item: dict) -> dict:
    """Simulate processing data."""
    await asyncio.sleep(random.uniform(0.1, 0.2))
    if random.random() < 0.05:
        raise ValueError("Processing error")
    item["processed"] = True
    return item


async def save_data(item: dict) -> str:
    """Simulate saving data."""
    await asyncio.sleep(random.uniform(0.05, 0.15))
    return f"saved_{item['id']}"


async def run_with_progress():
    """Run with minimal progress bar."""
    print("\n" + "=" * 60)
    print("1. PROGRESS BAR (progress=True)")
    print("=" * 60)
    print("Minimal terminal progress bar, no Rich panels.\n")

    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=3, tasks=[fetch_data], task_attempts=2),
            Stage(name="Process", workers=2, tasks=[process_data], task_attempts=2),
            Stage(name="Save", workers=2, tasks=[save_data]),
        ]
    )

    results = await pipeline.run(list(range(30)), progress=True)
    print(f"\nProcessed: {len(results)} items")


async def run_with_compact():
    """Run with compact dashboard."""
    print("\n" + "=" * 60)
    print("2. COMPACT DASHBOARD (dashboard='compact')")
    print("=" * 60)
    print("Single panel with progress, rate, ETA, and counts.\n")
    input("Press Enter to start...")

    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=3, tasks=[fetch_data], task_attempts=2),
            Stage(name="Process", workers=2, tasks=[process_data], task_attempts=2),
            Stage(name="Save", workers=2, tasks=[save_data]),
        ]
    )

    results = await pipeline.run(list(range(30)), dashboard="compact")
    print(f"Processed: {len(results)} items")


async def run_with_detailed():
    """Run with detailed dashboard."""
    print("\n" + "=" * 60)
    print("3. DETAILED DASHBOARD (dashboard='detailed')")
    print("=" * 60)
    print("Shows per-stage metrics, worker counts, and performance.\n")
    input("Press Enter to start...")

    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=4, tasks=[fetch_data], task_attempts=2),
            Stage(name="Process", workers=3, tasks=[process_data], task_attempts=2),
            Stage(name="Save", workers=2, tasks=[save_data]),
        ]
    )

    results = await pipeline.run(list(range(30)), dashboard="detailed")
    print(f"Processed: {len(results)} items")


async def run_with_full():
    """Run with full dashboard."""
    print("\n" + "=" * 60)
    print("4. FULL DASHBOARD (dashboard='full')")
    print("=" * 60)
    print("Complete monitoring with worker status and item tracking.")
    print("Note: Item tracking requires StatusTracker.\n")
    input("Press Enter to start...")

    tracker = StatusTracker()
    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=4, tasks=[fetch_data], task_attempts=2),
            Stage(name="Process", workers=3, tasks=[process_data], task_attempts=2),
            Stage(name="Save", workers=2, tasks=[save_data]),
        ],
        status_tracker=tracker,
    )

    results = await pipeline.run(list(range(30)), dashboard="full")

    summary = pipeline.get_error_summary()
    print(f"Processed: {len(results)} items")
    print(f"Failed: {summary.total_failed} items")
    if summary.errors_by_type:
        print("Errors by type:")
        for error_type, count in summary.errors_by_type.items():
            print(f"  {error_type}: {count}")


async def main():
    print("=" * 60)
    print("AntFlow Dashboard Levels Demo")
    print("=" * 60)
    print("\nThis demo shows the different visualization options.")
    print("Run each one to see how they differ.\n")

    print("Options:")
    print("  1. progress=True  - Minimal progress bar")
    print("  2. compact        - Single panel with essentials")
    print("  3. detailed       - Per-stage metrics")
    print("  4. full           - Complete monitoring")
    print("  5. Run all")
    print()

    choice = input("Choose option (1-5): ").strip()

    if choice == "1":
        await run_with_progress()
    elif choice == "2":
        await run_with_compact()
    elif choice == "3":
        await run_with_detailed()
    elif choice == "4":
        await run_with_full()
    elif choice == "5":
        await run_with_progress()
        await run_with_compact()
        await run_with_detailed()
        await run_with_full()
    else:
        print("Invalid choice. Running progress bar demo.")
        await run_with_progress()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
