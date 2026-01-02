"""
StatusTracker monitoring example.

Demonstrates comprehensive status tracking including:
- Item status queries (get_status, get_by_status, get_stats, get_history)
- Status change callbacks (on_status_change)
- Task-level event callbacks (on_task_start, on_task_complete, on_task_retry, on_task_fail)

This example combines item-level and task-level monitoring in a single pipeline.
"""

import asyncio

from antflow import Pipeline, Stage, StatusEvent, StatusTracker, TaskEvent


async def fetch_data(x: int) -> dict:
    """Simulate fetching data from an API."""
    await asyncio.sleep(0.05)
    return {"id": x, "data": f"fetched_{x}"}


async def validate(data: dict) -> dict:
    """Validate fetched data (fails for multiples of 7)."""
    await asyncio.sleep(0.03)
    if data["id"] % 7 == 0:
        raise ValueError(f"Validation failed for item {data['id']}")
    data["validated"] = True
    return data


async def transform(data: dict) -> dict:
    """Transform data (fails for multiples of 11)."""
    await asyncio.sleep(0.04)
    if data["id"] % 11 == 0:
        raise RuntimeError(f"Transform error for item {data['id']}")
    data["transformed"] = data["data"].upper()
    return data


async def save_data(data: dict) -> dict:
    """Save data to database."""
    await asyncio.sleep(0.03)
    data["saved"] = True
    return data


task_stats = {
    "fetch_data": {"completed": 0, "retries": 0, "failures": 0},
    "validate": {"completed": 0, "retries": 0, "failures": 0},
    "transform": {"completed": 0, "retries": 0, "failures": 0},
    "save_data": {"completed": 0, "retries": 0, "failures": 0},
}


async def on_status_change(event: StatusEvent):
    """Handle item status changes."""
    if event.status == "failed":
        error = event.metadata.get("error", "Unknown")
        print(f"❌ Item {event.item_id} failed @ {event.stage}: {error}")
    elif event.status == "retrying":
        attempt = event.metadata.get("attempt", "?")
        print(f"🔄 Item {event.item_id} retrying @ {event.stage} (attempt {attempt})")


async def on_task_start(event: TaskEvent):
    """Called when a task starts executing."""
    pass


async def on_task_complete(event: TaskEvent):
    """Called when a task completes successfully."""
    task_stats[event.task_name]["completed"] += 1


async def on_task_retry(event: TaskEvent):
    """Called when a task is retrying after failure."""
    task_stats[event.task_name]["retries"] += 1
    print(f"⚠️  Task {event.task_name} retry #{event.attempt} for item {event.item_id}")
    print(f"   Error: {event.error}")


async def on_task_fail(event: TaskEvent):
    """Called when a task fails after all retries."""
    task_stats[event.task_name]["failures"] += 1
    print(f"💀 Task {event.task_name} FAILED for item {event.item_id} after {event.attempt} attempts")


async def monitor_loop(tracker: StatusTracker, interval: float = 0.3):
    """Real-time status monitor using polling."""
    while True:
        await asyncio.sleep(interval)
        stats = tracker.get_stats()

        total = sum(stats.values())
        if total == 0:
            continue

        print(
            f"\r📊 Queued: {stats['queued']:2d} | "
            f"In Progress: {stats['in_progress']:2d} | "
            f"Completed: {stats['completed']:2d} | "
            f"Failed: {stats['failed']:2d}",
            end="",
            flush=True
        )

        if stats["in_progress"] == 0 and stats["queued"] == 0:
            print()
            break


async def main():
    print("=" * 60)
    print("StatusTracker Monitoring Example")
    print("=" * 60)
    print()
    print("Features demonstrated:")
    print("  - on_status_change callback for item events")
    print("  - on_task_* callbacks for task-level events")
    print("  - Real-time status polling with get_stats()")
    print("  - Query methods: get_status(), get_by_status(), get_history()")
    print()

    tracker = StatusTracker(
        on_status_change=on_status_change,
        on_task_start=on_task_start,
        on_task_complete=on_task_complete,
        on_task_retry=on_task_retry,
        on_task_fail=on_task_fail
    )

    stage = Stage(
        name="ETL",
        workers=3,
        tasks=[fetch_data, validate, transform, save_data],
        retry="per_task",
        task_attempts=2,
        task_wait_seconds=0.1
    )

    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    items = list(range(20))
    print(f"Processing {len(items)} items through 4-task pipeline...\n")

    async with asyncio.TaskGroup() as tg:
        tg.create_task(monitor_loop(tracker))
        await pipeline.run(items)

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    final_stats = tracker.get_stats()
    print("\n📊 Final Status:")
    print(f"   Completed: {final_stats['completed']}")
    print(f"   Failed: {final_stats['failed']}")

    print("\n📊 Task Statistics:")
    print(f"   {'Task':<12} {'Done':<8} {'Retries':<8} {'Failed':<8}")
    print("   " + "-" * 36)
    for task_name, stats in task_stats.items():
        print(f"   {task_name:<12} {stats['completed']:<8} {stats['retries']:<8} {stats['failures']:<8}")

    print("\n📋 Query Examples:")

    item_id = 1
    status = tracker.get_status(item_id)
    if status:
        print(f"   get_status({item_id}): {status.status} @ {status.stage}")

    failed_items = tracker.get_by_status("failed")
    print(f"   get_by_status('failed'): {len(failed_items)} items")

    history = tracker.get_history(0)
    print(f"   get_history(0): {len(history)} events")
    for event in history[:3]:
        print(f"      - {event.status} @ {event.stage or 'N/A'}")


if __name__ == "__main__":
    asyncio.run(main())
