"""
Worker monitoring example.

Demonstrates pipeline worker monitoring including:
- get_worker_states(): Current status of each worker (idle/busy)
- get_worker_metrics(): Performance metrics per worker
- get_dashboard_snapshot(): Complete pipeline snapshot
- Worker distribution tracking via on_status_change callback

This example shows how to monitor worker activity and utilization in real-time.
"""

import asyncio
from collections import defaultdict

from antflow import Pipeline, Stage, StatusEvent, StatusTracker


async def process_item(x: int) -> int:
    """Process an item with variable delay based on value."""
    delay = 0.1 + (x % 5) * 0.05
    await asyncio.sleep(delay)
    return x * 2


async def monitor_workers(pipeline: Pipeline, interval: float = 0.3):
    """Real-time worker monitoring loop."""
    while True:
        await asyncio.sleep(interval)

        states = pipeline.get_worker_states()
        stats = pipeline.get_stats()

        busy_count = sum(1 for s in states.values() if s.status == "busy")

        print(
            f"\r[Monitor] Workers: {busy_count}/{len(states)} busy | "
            f"Processed: {stats.items_processed} | "
            f"In flight: {stats.items_in_flight}",
            end="",
            flush=True
        )

        if stats.items_in_flight == 0 and busy_count == 0:
            print()
            break


async def main():
    print("=" * 60)
    print("Worker Monitoring Example")
    print("=" * 60)
    print()
    print("Features demonstrated:")
    print("  - get_worker_states(): Worker idle/busy status")
    print("  - get_worker_metrics(): Items processed, avg time per worker")
    print("  - get_dashboard_snapshot(): Complete pipeline state")
    print("  - Item-to-worker distribution via callbacks")
    print()

    worker_distribution = defaultdict(list)

    async def on_status_change(event: StatusEvent):
        """Track which worker processed each item."""
        if event.status == "in_progress" and event.worker:
            worker_distribution[event.worker].append(event.item_id)

    tracker = StatusTracker(on_status_change=on_status_change)

    stage = Stage(
        name="Process",
        workers=4,
        tasks=[process_item]
    )

    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    print(f"Workers: {pipeline.get_worker_names()}\n")

    items = list(range(25))

    monitor_task = asyncio.create_task(monitor_workers(pipeline))

    print("Processing items...")
    results = await pipeline.run(items)

    await monitor_task

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    print(f"\n✅ Processed {len(results)} items")

    print("\n📊 Worker States (final):")
    for name, state in sorted(pipeline.get_worker_states().items()):
        print(f"   {name}: {state.status}")

    print("\n📊 Worker Metrics:")
    for name, metric in sorted(pipeline.get_worker_metrics().items()):
        print(
            f"   {name}: "
            f"{metric.items_processed} items, "
            f"{metric.items_failed} failed, "
            f"avg {metric.avg_processing_time:.3f}s"
        )

    print("\n📊 Worker Distribution (items per worker):")
    for worker_name in sorted(worker_distribution.keys()):
        items_list = worker_distribution[worker_name]
        print(f"   {worker_name}: {len(items_list)} items")

    print("\n📊 Dashboard Snapshot:")
    snapshot = pipeline.get_dashboard_snapshot()
    print(f"   Timestamp: {snapshot.timestamp:.2f}")
    print(f"   Total workers: {len(snapshot.worker_states)}")
    print(f"   Items processed: {snapshot.pipeline_stats.items_processed}")
    print(f"   Items failed: {snapshot.pipeline_stats.items_failed}")
    print(f"   Queue sizes: {snapshot.pipeline_stats.queue_sizes}")


if __name__ == "__main__":
    asyncio.run(main())
