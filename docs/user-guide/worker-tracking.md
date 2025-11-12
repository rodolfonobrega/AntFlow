# Worker Tracking

Track which specific worker is processing each item in your pipeline for detailed monitoring and debugging.

## Overview

Each worker in a pipeline stage has a unique ID (0 to N-1). The `StatusEvent.worker_id` property allows you to track which worker is processing each item.

## Worker IDs

Worker IDs are zero-indexed integers:

- Stage with 1 worker: worker ID `0`
- Stage with 3 workers: worker IDs `0`, `1`, `2`
- Stage with 10 workers: worker IDs `0` through `9`

### Worker Naming Convention

Workers are internally named using the pattern `{StageName}-W{WorkerID}`:

- `"Fetch-W0"` - Worker 0 in Fetch stage
- `"Process-W5"` - Worker 5 in Process stage
- `"Transform-W12"` - Worker 12 in Transform stage

The `worker_id` property extracts the numeric ID from the worker name.

## Getting Worker Names

Use `pipeline.get_worker_names()` to get all worker names before running:

```python
from antflow import Pipeline, Stage

stage1 = Stage(name="Fetch", workers=3, tasks=[fetch_data])
stage2 = Stage(name="Process", workers=5, tasks=[process_data])

pipeline = Pipeline(stages=[stage1, stage2])

worker_names = pipeline.get_worker_names()
print(worker_names)
# {
#     "Fetch": ["Fetch-W0", "Fetch-W1", "Fetch-W2"],
#     "Process": ["Process-W0", "Process-W1", "Process-W2", "Process-W3", "Process-W4"]
# }
```

This is useful for:

- Setting up monitoring dashboards before pipeline runs
- Pre-allocating tracking structures
- Understanding pipeline topology

## Tracking Worker Assignments

Track which worker processes which item:

```python
from antflow import StatusTracker
from collections import defaultdict

item_to_worker = {}
worker_activity = defaultdict(list)

async def on_status_change(event):
    if event.status == "in_progress":
        item_to_worker[event.item_id] = event.worker_id
        worker_activity[event.worker_id].append(event.item_id)
        print(f"Worker {event.worker_id} started processing {event.item_id}")

tracker = StatusTracker(on_status_change=on_status_change)
pipeline = Pipeline(stages=[stage], status_tracker=tracker)

results = await pipeline.run(items)

for worker_id in sorted(worker_activity.keys()):
    items_count = len(worker_activity[worker_id])
    print(f"Worker {worker_id} processed {items_count} items")
```

## Custom Item IDs

By default, items are assigned sequential IDs (0, 1, 2, ...). You can provide custom IDs for better tracking.

### Using Custom IDs

Pass items as dictionaries with an `"id"` field:

```python
items = [
    {"id": "batch_0001", "value": data1},
    {"id": "batch_0002", "value": data2},
    {"id": "user_12345", "value": user_data},
]

results = await pipeline.run(items)
```

Now you can track: `"batch_0001 was processed by Worker 5"`

### Without Custom IDs

For simple use cases, just pass values directly:

```python
items = [data1, data2, data3]
results = await pipeline.run(items)
```

Items will be tracked as `0`, `1`, `2`, etc.

## Use Cases

### 1. Worker Load Balancing Analysis

Identify if work is distributed evenly:

```python
from collections import defaultdict

worker_times = defaultdict(list)

async def track_performance(event):
    if event.status == "in_progress":
        start_times[event.item_id] = event.timestamp
    elif event.status == "completed":
        duration = event.timestamp - start_times[event.item_id]
        worker_times[event.worker_id].append(duration)

tracker = StatusTracker(on_status_change=track_performance)

for worker_id, times in worker_times.items():
    avg_time = sum(times) / len(times)
    print(f"Worker {worker_id}: avg {avg_time:.2f}s per item")
```

### 2. Live Dashboard

Display real-time worker activity:

```python
from antflow import StatusTracker

async def update_worker_dashboard(event):
    if event.status == "in_progress":
        await websocket.send_json({
            "worker_id": event.worker_id,
            "worker_name": event.worker,
            "item_id": event.item_id,
            "stage": event.stage,
            "timestamp": event.timestamp
        })

tracker = StatusTracker(on_status_change=update_worker_dashboard)
```

### 3. Error Tracking by Worker

Identify problematic workers:

```python
from collections import defaultdict

worker_errors = defaultdict(int)

async def track_errors(event):
    if event.status == "failed" and event.worker_id is not None:
        worker_errors[event.worker_id] += 1
        error = event.metadata.get("error", "Unknown")
        print(f"Worker {event.worker_id} error: {error}")

tracker = StatusTracker(on_status_change=track_errors)

for worker_id, error_count in worker_errors.items():
    print(f"Worker {worker_id} had {error_count} errors")
```

### 4. Worker Utilization Metrics

Track worker efficiency:

```python
from collections import defaultdict

worker_stats = defaultdict(lambda: {"completed": 0, "failed": 0})

async def track_utilization(event):
    if event.status in ("completed", "failed") and event.worker_id is not None:
        worker_stats[event.worker_id][event.status] += 1

tracker = StatusTracker(on_status_change=track_utilization)

for worker_id, stats in sorted(worker_stats.items()):
    total = stats["completed"] + stats["failed"]
    success_rate = (stats["completed"] / total * 100) if total > 0 else 0
    print(f"Worker {worker_id}: {stats['completed']}/{total} ({success_rate:.1f}%)")
```

## Complete Example

```python
import asyncio
from collections import defaultdict
from antflow import Pipeline, Stage, StatusTracker

async def process_batch(batch_data):
    await asyncio.sleep(0.2)
    return f"processed_{batch_data}"

async def main():
    item_to_worker = {}
    worker_activity = defaultdict(list)

    async def on_status_change(event):
        if event.status == "in_progress":
            item_to_worker[event.item_id] = event.worker_id
            worker_activity[event.worker_id].append(event.item_id)
            print(f"[Worker {event.worker_id:2d}] Processing {event.item_id}")
        elif event.status == "completed":
            print(f"[Worker {event.worker_id:2d}] Completed {event.item_id}")

    tracker = StatusTracker(on_status_change=on_status_change)

    stage = Stage(name="ProcessBatch", workers=5, tasks=[process_batch])
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
        print(f"Worker {worker_id}: {len(items_processed)} items")

asyncio.run(main())
```

## Key Points

- **Worker IDs are 0-indexed**: First worker is `0`, not `1`
- **Custom IDs are optional**: Use them only if you need tracking
- **Worker names available before run**: Use `get_worker_names()` for setup
- **Property extraction**: `worker_id` is extracted from `worker` name automatically
- **Stage-specific**: Each stage has its own set of worker IDs starting from 0

## Next Steps

- Learn about [Error Handling](error-handling.md)
- Explore [Advanced Pipeline Usage](pipeline.md)
- See [Examples](../examples/basic.md)
