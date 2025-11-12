"""
Status tracking example showing real-time monitoring of pipeline items.
"""

import asyncio

from antflow import Pipeline, Stage, StatusEvent, StatusTracker


async def fetch_data(x: int) -> dict:
    """Simulate fetching data from an API."""
    await asyncio.sleep(0.1)
    return {"id": x, "data": f"fetched_{x}"}


async def process_data(data: dict) -> dict:
    """Simulate processing data."""
    await asyncio.sleep(0.15)
    data["processed"] = data["data"].upper()
    return data


async def failing_task(data: dict) -> dict:
    """Task that fails for some items."""
    await asyncio.sleep(0.1)
    if data["id"] % 7 == 0:
        raise ValueError(f"Failed to process item {data['id']}")
    return data


async def save_data(data: dict) -> dict:
    """Simulate saving data to database."""
    await asyncio.sleep(0.1)
    data["saved"] = True
    return data


async def monitor_status(tracker: StatusTracker, interval: float = 0.5):
    """Monitor and print status statistics in real-time."""
    print("\n=== Real-time Status Monitor ===\n")

    while True:
        await asyncio.sleep(interval)
        stats = tracker.get_stats()

        total = sum(stats.values())
        if total == 0:
            continue

        print(f"\r📊 Status: "
              f"⏳ Queued: {stats['queued']:3d} | "
              f"⚙️  In Progress: {stats['in_progress']:3d} | "
              f"✅ Completed: {stats['completed']:3d} | "
              f"❌ Failed: {stats['failed']:3d} | "
              f"Total: {total:3d}", end="", flush=True)

        if stats['in_progress'] == 0 and stats['queued'] == 0:
            print()
            break


async def track_events(event: StatusEvent):
    """Track individual status change events."""
    status_icons = {
        "queued": "⏳",
        "in_progress": "⚙️",
        "completed": "✅",
        "failed": "❌"
    }

    icon = status_icons.get(event.status, "❓")

    if event.status == "failed":
        error = event.metadata.get("error", "Unknown error")
        print(f"{icon} Item {event.item_id} @ {event.stage}: {event.status} - {error}")
    elif event.metadata.get("retry"):
        attempt = event.metadata.get("attempt", "?")
        print(f"{icon} Item {event.item_id} @ {event.stage}: retry (attempt {attempt})")


async def main():
    print("=== Status Tracking Example ===\n")

    tracker = StatusTracker()

    fetch_stage = Stage(
        name="Fetch",
        workers=3,
        tasks=[fetch_data],
        retry="per_task",
        task_attempts=2
    )

    process_stage = Stage(
        name="Process",
        workers=2,
        tasks=[process_data, failing_task],
        retry="per_task",
        task_attempts=1
    )

    save_stage = Stage(
        name="Save",
        workers=2,
        tasks=[save_data],
        retry="per_task",
        task_attempts=3
    )

    pipeline = Pipeline(
        stages=[fetch_stage, process_stage, save_stage],
        status_tracker=tracker
    )

    items = list(range(20))
    print(f"Processing {len(items)} items through 3-stage pipeline\n")

    async with asyncio.TaskGroup() as tg:
        tg.create_task(monitor_status(tracker))
        await pipeline.run(items)

    print("\n\n=== Final Statistics ===\n")
    stats = tracker.get_stats()
    print(f"✅ Completed: {stats['completed']}")
    print(f"❌ Failed: {stats['failed']}")
    print(f"Total processed: {stats['completed'] + stats['failed']}")

    print("\n=== Failed Items ===\n")
    failed_events = tracker.get_by_status("failed")
    if failed_events:
        for event in failed_events:
            error = event.metadata.get("error", "Unknown")
            print(f"  Item {event.item_id} @ {event.stage}: {error}")
    else:
        print("  No failures!")

    print("\n=== Sample Event History ===\n")
    sample_item_id = 0
    history = tracker.get_history(sample_item_id)
    print(f"Event history for item {sample_item_id}:")
    for event in history:
        print(f"  {event.status:12s} @ {event.stage or 'N/A':10s} "
              f"(timestamp: {event.timestamp:.2f})")

    print("\n=== Items by Status ===\n")
    for status in ["completed", "failed", "queued", "in_progress"]:
        items_with_status = tracker.get_by_status(status)
        print(f"{status.capitalize():12s}: {len(items_with_status)} items")

    print("\n=== Query Example ===\n")
    item_id = 5
    status = tracker.get_status(item_id)
    if status:
        print(f"Item {item_id} current status: {status.status} @ {status.stage}")
    else:
        print(f"Item {item_id} not found")

    print("\n✅ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
