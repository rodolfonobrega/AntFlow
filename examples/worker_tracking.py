"""
Worker tracking example showing how to monitor which worker processes each item.
"""

import asyncio
from collections import defaultdict

from antflow import Pipeline, Stage, StatusTracker


async def process_batch(batch_data):
    """Simulate batch processing with variable duration."""
    await asyncio.sleep(0.2)
    return f"processed_{batch_data}"


async def main():
    print("=== Worker Tracking Example ===\n")

    item_to_worker = {}
    worker_activity = defaultdict(list)

    async def on_status_change(event):
        if event.status == "in_progress" and event.worker_id is not None:
            item_to_worker[event.item_id] = event.worker_id
            worker_activity[event.worker_id].append(event.item_id)
            print(f"[Worker {event.worker_id:2d}] Processing {event.item_id}")
        elif event.status == "completed" and event.worker_id is not None:
            print(f"[Worker {event.worker_id:2d}] Completed {event.item_id}")

    tracker = StatusTracker(on_status_change=on_status_change)

    stage = Stage(
        name="ProcessBatch",
        workers=5,
        tasks=[process_batch]
    )

    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    worker_names = pipeline.get_worker_names()
    print(f"Available workers: {worker_names}\n")

    items = [
        {"id": f"batch_{i:04d}", "value": f"data_{i}"}
        for i in range(20)
    ]

    results = await pipeline.run(items)

    print("\n=== Worker Utilization ===")
    for worker_id in sorted(worker_activity.keys()):
        items_processed = worker_activity[worker_id]
        print(f"Worker {worker_id}: {len(items_processed)} items - {items_processed}")

    print("\n=== Item to Worker Mapping (sample) ===")
    for item_id in list(item_to_worker.keys())[:5]:
        worker_id = item_to_worker[item_id]
        print(f"{item_id} was processed by Worker {worker_id}")

    print(f"\n✅ Processed {len(results)} items successfully")


if __name__ == "__main__":
    asyncio.run(main())
