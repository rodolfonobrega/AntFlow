"""
Advanced Pipeline example with StatusTracker, retry strategies, and error handling.
"""

import asyncio
import random

from antflow import Pipeline, Stage, StatusEvent, StatusTracker


async def fetch_api_data(item_id: int) -> dict:
    """Simulate fetching data from an API (may fail randomly)."""
    await asyncio.sleep(0.05)
    if random.random() < 0.2:
        raise ConnectionError(f"API connection failed for item {item_id}")
    return {"id": item_id, "data": f"raw_data_{item_id}"}


async def validate_data(data: dict) -> dict:
    """Validate fetched data."""
    await asyncio.sleep(0.03)
    if "data" not in data:
        raise ValueError("Invalid data structure")
    data["validated"] = True
    return data


async def enrich_data(data: dict) -> dict:
    """Enrich data with additional information."""
    await asyncio.sleep(0.04)
    data["enriched"] = f"enriched_{data['data']}"
    return data


async def save_to_database(data: dict) -> dict:
    """Simulate saving to database (may fail randomly)."""
    await asyncio.sleep(0.06)
    if random.random() < 0.15:
        raise IOError(f"Database write failed for item {data['id']}")
    data["saved"] = True
    return data


async def on_status_change(event: StatusEvent):
    """
    Status change handler for monitoring all pipeline events.
    """
    if event.status == "completed":
        print(f"  ✅ Completed item {event.item_id} @ {event.stage}")
    elif event.status == "failed":
        error = event.metadata.get("error", "Unknown error")
        print(f"  ❌ Failed item {event.item_id} @ {event.stage}: {error}")
    elif event.status == "queued" and event.metadata.get("retry"):
        attempt = event.metadata.get("attempt", "?")
        print(f"  🔄 Retrying item {event.item_id} @ {event.stage} (attempt {attempt})")
    elif event.status == "in_progress":
        print(f"  ⚙️  Processing item {event.item_id} @ {event.stage} (worker: {event.worker})")


async def main():
    print("=== Advanced Pipeline Example ===\n")
    print("This example demonstrates:")
    print("- StatusTracker for real-time status monitoring")
    print("- Multiple stages with different retry strategies")
    print("- Error handling and recovery")
    print("- Random failures to showcase retry behavior\n")

    tracker = StatusTracker(on_status_change=on_status_change)

    fetch_stage = Stage(
        name="Fetch",
        workers=3,
        tasks=[fetch_api_data],
        retry="per_stage",
        stage_attempts=3
    )

    process_stage = Stage(
        name="Process",
        workers=2,
        tasks=[validate_data, enrich_data],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=0.5
    )

    save_stage = Stage(
        name="Save",
        workers=2,
        tasks=[save_to_database],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=1.0
    )

    async with Pipeline(
        stages=[fetch_stage, process_stage, save_stage],
        status_tracker=tracker
    ) as pipeline:
        items = list(range(15))
        print(f"Processing {len(items)} items...\n")

        results = await pipeline.run(items)

        print(f"\n{'='*50}")
        print("Pipeline Complete!")
        print(f"{'='*50}")

        pipeline_stats = pipeline.get_stats()
        print("\n📊 Pipeline Statistics:")
        print(f"  Items processed: {pipeline_stats.items_processed}")
        print(f"  Items failed: {pipeline_stats.items_failed}")
        total_items = pipeline_stats.items_processed + pipeline_stats.items_failed
        success_rate = (
            (pipeline_stats.items_processed / total_items * 100)
            if total_items > 0
            else 0
        )
        print(f"  Success rate: {success_rate:.1f}%")

        tracker_stats = tracker.get_stats()
        print("\n📊 Tracker Statistics:")
        print(f"  Completed: {tracker_stats['completed']}")
        print(f"  Failed: {tracker_stats['failed']}")
        print(f"  In Progress: {tracker_stats['in_progress']}")
        print(f"  Queued: {tracker_stats['queued']}")

        print(f"\n✅ Successful results: {len(results)}")
        if results:
            print("\nSample results (first 3):")
            for result in results[:3]:
                print(f"  Item {result.id}: {result.value}")

        failed_items = tracker.get_by_status("failed")
        if failed_items:
            print(f"\n❌ Failed items: {len(failed_items)}")
            for event in failed_items[:3]:
                error = event.metadata.get("error", "Unknown")
                print(f"  Item {event.item_id} @ {event.stage}: {error}")


if __name__ == "__main__":
    random.seed(42)
    asyncio.run(main())
