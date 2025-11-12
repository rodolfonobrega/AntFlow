"""
Task-level tracking example showing granular monitoring of individual tasks.

Demonstrates how to track retries and failures at the task level,
not just at the stage level.
"""

import asyncio

from antflow import Pipeline, Stage, StatusTracker, TaskEvent


async def validate(x: int) -> int:
    """Validate input (fails for specific values)."""
    await asyncio.sleep(0.02)
    if x % 7 == 0:
        raise ValueError(f"Validation failed for {x}")
    return x


async def transform(x: int) -> int:
    """Transform data (can fail intermittently)."""
    await asyncio.sleep(0.03)
    if x % 11 == 0:
        raise RuntimeError(f"Transform error for {x}")
    return x * 2


async def enrich(x: int) -> int:
    """Enrich with additional data."""
    await asyncio.sleep(0.02)
    return x + 100


async def save(x: int) -> int:
    """Save to database (fails occasionally)."""
    await asyncio.sleep(0.04)
    if x > 200:
        raise IOError(f"Database error for {x}")
    return x


task_stats = {
    "validate": {"retries": 0, "failures": 0},
    "transform": {"retries": 0, "failures": 0},
    "enrich": {"retries": 0, "failures": 0},
    "save": {"retries": 0, "failures": 0}
}


async def on_task_start(event: TaskEvent):
    """Called when a task starts."""
    pass


async def on_task_complete(event: TaskEvent):
    """Called when a task completes successfully."""
    print(f"✅ {event.task_name} completed for item {event.item_id} "
          f"in {event.duration:.3f}s (attempt {event.attempt})")


async def on_task_retry(event: TaskEvent):
    """Called when a task is retrying after failure."""
    task_stats[event.task_name]["retries"] += 1
    print(f"⚠️  {event.task_name} retry #{event.attempt} for item {event.item_id}")
    print(f"   Error: {event.error}")
    print(f"   Duration before retry: {event.duration:.3f}s")


async def on_task_fail(event: TaskEvent):
    """Called when a task fails after all retries."""
    task_stats[event.task_name]["failures"] += 1
    print(f"❌ {event.task_name} FAILED for item {event.item_id} "
          f"after {event.attempt} attempts")
    print(f"   Error: {event.error}")
    print(f"   Duration: {event.duration:.3f}s")

    if event.task_name == "save":
        print(f"   🚨 CRITICAL: Database save failed!")


async def main():
    print("=== Task-Level Tracking Example ===\n")
    print("Processing items through a 4-task pipeline:")
    print("  1. validate -> 2. transform -> 3. enrich -> 4. save\n")

    tracker = StatusTracker(
        on_task_start=on_task_start,
        on_task_complete=on_task_complete,
        on_task_retry=on_task_retry,
        on_task_fail=on_task_fail
    )

    stage = Stage(
        name="ETL",
        workers=3,
        tasks=[validate, transform, enrich, save],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=0.1
    )

    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    items = list(range(25))
    print(f"Processing {len(items)} items...\n")

    results = await pipeline.run(items)

    print(f"\n{'='*60}")
    print("Results")
    print(f"{'='*60}\n")

    print(f"✅ Successfully processed: {len(results)}/{len(items)} items\n")

    print("Task Statistics:")
    print(f"{'Task':<12} {'Retries':<10} {'Failures':<10}")
    print("-" * 32)
    for task_name, stats in task_stats.items():
        print(f"{task_name:<12} {stats['retries']:<10} {stats['failures']:<10}")

    total_retries = sum(s["retries"] for s in task_stats.values())
    total_failures = sum(s["failures"] for s in task_stats.values())

    print(f"\nTotal retries: {total_retries}")
    print(f"Total failures: {total_failures}")

    if task_stats["save"]["failures"] > 0:
        print(f"\n⚠️  Database save had {task_stats['save']['failures']} failures!")
        print("Consider:")
        print("  - Increasing retry attempts for save task")
        print("  - Adding exponential backoff")
        print("  - Implementing dead letter queue")


if __name__ == "__main__":
    asyncio.run(main())
