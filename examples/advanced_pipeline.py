"""
Advanced Pipeline example with StatusTracker, retry strategies, and error handling.

This example shows TWO equivalent ways to build the same pipeline:
1. Using Stage objects (explicit, full control)
2. Using Pipeline.create().add() (fluent, concise)

Both produce identical results - choose based on your preference.
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
    """Status change handler for monitoring all pipeline events."""
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


async def run_with_stage_objects():
    """
    METHOD 1: Using Stage objects (explicit, full control)

    Use this when you need:
    - Fine-grained control over retry strategies
    - Different retry modes per stage (per_stage vs per_task)
    - Custom wait times between retries
    - Task concurrency limits
    """
    print("\n" + "=" * 60)
    print("METHOD 1: Using Stage objects")
    print("=" * 60)

    tracker = StatusTracker(on_status_change=on_status_change)

    fetch_stage = Stage(
        name="Fetch",
        workers=3,
        tasks=[fetch_api_data],
        retry="per_stage",
        stage_attempts=3,
    )

    process_stage = Stage(
        name="Process",
        workers=2,
        tasks=[validate_data, enrich_data],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=0.5,
    )

    save_stage = Stage(
        name="Save",
        workers=2,
        tasks=[save_to_database],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=1.0,
    )

    pipeline = Pipeline(
        stages=[fetch_stage, process_stage, save_stage],
        status_tracker=tracker,
    )

    return pipeline, tracker


async def run_with_fluent_api():
    """
    METHOD 2: Using Pipeline.create().add() (fluent, concise)

    Use this when you want:
    - Concise, readable pipeline definitions
    - Quick prototyping
    - Chainable configuration

    Note: The fluent API uses simpler retry configuration.
    For advanced retry strategies (per_stage, custom wait times),
    use Stage objects directly.
    """
    print("\n" + "=" * 60)
    print("METHOD 2: Using Pipeline.create().add() - Fluent API")
    print("=" * 60)

    tracker = StatusTracker(on_status_change=on_status_change)

    pipeline = (
        Pipeline.create()
        .add("Fetch", fetch_api_data, workers=3, retries=3)
        .add("Process", validate_data, enrich_data, workers=2, retries=3)
        .add("Save", save_to_database, workers=2, retries=5)
        .with_tracker(tracker)
        .build()
    )

    return pipeline, tracker


async def run_pipeline(pipeline: Pipeline, tracker: StatusTracker, items: list):
    """Run the pipeline and display results."""
    print(f"\nProcessing {len(items)} items...\n")

    results = await pipeline.run(items)

    print(f"\n{'=' * 50}")
    print("Pipeline Complete!")
    print(f"{'=' * 50}")

    pipeline_stats = pipeline.get_stats()
    print("\n📊 Pipeline Statistics:")
    print(f"  Items processed: {pipeline_stats.items_processed}")
    print(f"  Items failed: {pipeline_stats.items_failed}")
    total_items = pipeline_stats.items_processed + pipeline_stats.items_failed
    success_rate = (
        (pipeline_stats.items_processed / total_items * 100) if total_items > 0 else 0
    )
    print(f"  Success rate: {success_rate:.1f}%")

    tracker_stats = tracker.get_stats()
    print("\n📊 Tracker Statistics:")
    print(f"  Completed: {tracker_stats['completed']}")
    print(f"  Failed: {tracker_stats['failed']}")

    print(f"\n✅ Successful results: {len(results)}")
    if results:
        print("\nSample results (first 3):")
        for result in results[:3]:
            print(f"  Item {result.id}: {result.value}")

    return results


async def main():
    print("=" * 60)
    print("Advanced Pipeline Example")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("- StatusTracker for real-time status monitoring")
    print("- Multiple stages with different retry strategies")
    print("- Error handling and recovery")
    print("- TWO equivalent ways to build the same pipeline")

    items = list(range(15))

    # Run with Stage objects
    random.seed(42)
    pipeline1, tracker1 = await run_with_stage_objects()
    await run_pipeline(pipeline1, tracker1, items)

    # Run with fluent API
    random.seed(42)
    pipeline2, tracker2 = await run_with_fluent_api()
    await run_pipeline(pipeline2, tracker2, items)

    # Show equivalence
    print("\n" + "=" * 60)
    print("COMPARISON: Both methods are equivalent")
    print("=" * 60)
    print("""
    # Method 1: Stage objects (full control)
    fetch_stage = Stage(
        name="Fetch",
        workers=3,
        tasks=[fetch_api_data],
        retry="per_stage",      # ← Advanced: retry entire stage
        stage_attempts=3,
    )
    pipeline = Pipeline(stages=[fetch_stage, ...], status_tracker=tracker)

    # Method 2: Fluent API (concise)
    pipeline = (
        Pipeline.create()
        .add("Fetch", fetch_api_data, workers=3, retries=3)
        .with_tracker(tracker)
        .build()
    )

    When to use Stage objects:
    - Need per_stage retry (vs per_task)
    - Need custom wait times (task_wait_seconds)
    - Need task concurrency limits
    - Need on_success/on_failure callbacks

    When to use fluent API:
    - Quick prototyping
    - Simple retry configuration
    - Readable, chainable code
    """)

if __name__ == "__main__":
    asyncio.run(main())
