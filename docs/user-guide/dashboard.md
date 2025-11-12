# Dashboard and Real-Time Monitoring

AntFlow provides comprehensive tools for monitoring pipeline execution in real-time, including worker states, performance metrics, and dashboard helpers.

## Overview

The dashboard functionality provides:

- **Worker State Tracking**: Know what each worker is doing at any moment
- **Performance Metrics**: Track items processed, failures, and average processing time per worker
- **Snapshot API**: Query current state for dashboards and UIs
- **Event Streaming**: Subscribe to real-time status changes
- **PipelineDashboard Helper**: Combines queries and events for efficient monitoring

## Quick Start

```python
from antflow import Pipeline, PipelineDashboard, Stage, StatusTracker

tracker = StatusTracker()
stage = Stage(name="Process", workers=5, tasks=[my_task])
pipeline = Pipeline(stages=[stage], status_tracker=tracker)

dashboard = PipelineDashboard(pipeline, tracker)

snapshot = dashboard.get_snapshot()
print(f"Active workers: {len(dashboard.get_active_workers())}")
print(f"Items processed: {snapshot.pipeline_stats.items_processed}")
```

## Worker States

### Querying Worker States

Get the current state of all workers:

```python
states = pipeline.get_worker_states()

for worker_name, state in states.items():
    print(f"{worker_name}:")
    print(f"  Status: {state.status}")  # "idle" or "busy"
    print(f"  Current item: {state.current_item_id}")
    print(f"  Processing since: {state.processing_since}")
```

### Worker State Fields

Each `WorkerState` contains:

- **`worker_name`**: Full worker name (e.g., "Fetch-W0")
- **`stage`**: Stage name the worker belongs to
- **`status`**: Either `"idle"` or `"busy"`
- **`current_item_id`**: ID of item being processed (None if idle)
- **`processing_since`**: Timestamp when started processing current item

### Example: Finding Busy Workers

```python
states = pipeline.get_worker_states()

busy_workers = [
    (name, state.current_item_id)
    for name, state in states.items()
    if state.status == "busy"
]

print(f"Busy workers: {len(busy_workers)}")
for worker, item_id in busy_workers:
    print(f"  {worker} processing item {item_id}")
```

## Worker Metrics

### Querying Performance Metrics

Get performance metrics for all workers:

```python
metrics = pipeline.get_worker_metrics()

for worker_name, metric in metrics.items():
    print(f"{worker_name}:")
    print(f"  Items processed: {metric.items_processed}")
    print(f"  Items failed: {metric.items_failed}")
    print(f"  Avg processing time: {metric.avg_processing_time:.3f}s")
    print(f"  Last active: {metric.last_active}")
```

### Worker Metrics Fields

Each `WorkerMetrics` contains:

- **`worker_name`**: Full worker name
- **`stage`**: Stage name
- **`items_processed`**: Count of successfully processed items
- **`items_failed`**: Count of failed items
- **`total_processing_time`**: Total time spent processing (seconds)
- **`last_active`**: Timestamp of last activity
- **`avg_processing_time`** (property): Average time per item

### Example: Top Performers

```python
metrics = pipeline.get_worker_metrics()

top_workers = sorted(
    metrics.items(),
    key=lambda x: x[1].items_processed,
    reverse=True
)[:5]

print("Top 5 workers:")
for worker, metric in top_workers:
    print(f"  {worker}: {metric.items_processed} items, "
          f"avg {metric.avg_processing_time:.3f}s")
```

## Dashboard Snapshots

### Getting Complete Snapshot

Get a complete snapshot of the current state:

```python
snapshot = pipeline.get_dashboard_snapshot()

print(f"Timestamp: {snapshot.timestamp}")
print(f"Active workers: {sum(1 for s in snapshot.worker_states.values() if s.status == 'busy')}")
print(f"Total processed: {snapshot.pipeline_stats.items_processed}")
print(f"Total failed: {snapshot.pipeline_stats.items_failed}")
print(f"Queue sizes: {snapshot.pipeline_stats.queue_sizes}")

for worker, metrics in snapshot.worker_metrics.items():
    if metrics.items_processed > 0:
        print(f"  {worker}: {metrics.items_processed} items")
```

### Snapshot Fields

A `DashboardSnapshot` contains:

- **`worker_states`**: Dict of all WorkerState objects
- **`worker_metrics`**: Dict of all WorkerMetrics objects
- **`pipeline_stats`**: PipelineStats (items processed/failed, queue sizes)
- **`timestamp`**: When snapshot was taken

## PipelineDashboard Helper

The `PipelineDashboard` class combines queries and events for efficient monitoring.

### Basic Usage

```python
from antflow import PipelineDashboard

dashboard = PipelineDashboard(
    pipeline=pipeline,
    tracker=tracker,
    on_update=my_update_callback,  # Optional
    update_interval=1.0  # Seconds between updates
)

snapshot = dashboard.get_snapshot()
active = dashboard.get_active_workers()
idle = dashboard.get_idle_workers()
utilization = dashboard.get_worker_utilization()
```

### Subscribing to Events

Subscribe to status change events:

```python
async def on_item_failed(event):
    if event.status == "failed":
        error = event.metadata.get("error")
        print(f"Item {event.item_id} failed: {error}")

dashboard.subscribe(on_item_failed)

await pipeline.run(items)

dashboard.unsubscribe(on_item_failed)
```

### Periodic Updates

Use automatic periodic updates for real-time dashboards:

```python
async def print_status(snapshot):
    active = sum(1 for s in snapshot.worker_states.values() if s.status == "busy")
    print(f"Active: {active}, Processed: {snapshot.pipeline_stats.items_processed}")

dashboard = PipelineDashboard(
    pipeline,
    tracker,
    on_update=print_status,
    update_interval=2.0
)

async with dashboard:
    await pipeline.run(items)
```

### Worker Utilization

Calculate success rate for each worker:

```python
utilization = dashboard.get_worker_utilization()

for worker, util in sorted(utilization.items()):
    print(f"{worker}: {util*100:.1f}% success rate")
```

## Real-Time Dashboard Example

### WebSocket Dashboard

```python
from fastapi import FastAPI, WebSocket
from antflow import Pipeline, PipelineDashboard, Stage, StatusTracker

app = FastAPI()

@app.websocket("/ws/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await websocket.accept()

    tracker = StatusTracker()
    pipeline = Pipeline(stages=[stage], status_tracker=tracker)
    dashboard = PipelineDashboard(pipeline, tracker)

    initial = dashboard.get_snapshot()
    await websocket.send_json({
        "type": "init",
        "workers": {
            name: {
                "status": state.status,
                "current_item": state.current_item_id
            }
            for name, state in initial.worker_states.items()
        },
        "stats": {
            "processed": initial.pipeline_stats.items_processed,
            "failed": initial.pipeline_stats.items_failed,
            "queues": initial.pipeline_stats.queue_sizes
        }
    })

    async def on_event(event):
        await websocket.send_json({
            "type": "event",
            "item_id": event.item_id,
            "status": event.status,
            "worker": event.worker,
            "timestamp": event.timestamp
        })

    dashboard.subscribe(on_event)

    asyncio.create_task(pipeline.run(items))
```

### Monitoring Loop

```python
async def monitor_pipeline(pipeline):
    while True:
        await asyncio.sleep(1.0)

        states = pipeline.get_worker_states()
        metrics = pipeline.get_worker_metrics()
        stats = pipeline.get_stats()

        busy_count = sum(1 for s in states.values() if s.status == "busy")

        print(f"\rActive: {busy_count}/{len(states)} | "
              f"Processed: {stats.items_processed} | "
              f"Failed: {stats.items_failed}",
              end="", flush=True)

        if stats.items_in_flight == 0 and busy_count == 0:
            break

asyncio.create_task(monitor_pipeline(pipeline))
await pipeline.run(items)
```

## Complete Example

```python
import asyncio
from antflow import Pipeline, PipelineDashboard, Stage, StatusTracker

async def process_item(x: int) -> int:
    await asyncio.sleep(0.1)
    return x * 2

async def print_updates(snapshot):
    active = sum(1 for s in snapshot.worker_states.values() if s.status == "busy")
    print(f"[{snapshot.timestamp:.1f}] Active: {active}, "
          f"Processed: {snapshot.pipeline_stats.items_processed}")

async def main():
    tracker = StatusTracker()

    stage = Stage(name="Process", workers=5, tasks=[process_item])
    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    dashboard = PipelineDashboard(
        pipeline,
        tracker,
        on_update=print_updates,
        update_interval=2.0
    )

    async with dashboard:
        print("Starting processing...")
        results = await pipeline.run(range(50))
        print(f"\nCompleted! Processed {len(results)} items")

    print("\nFinal metrics:")
    for worker, metrics in dashboard.get_worker_metrics().items():
        if metrics.items_processed > 0:
            print(f"  {worker}: {metrics.items_processed} items, "
                  f"avg {metrics.avg_processing_time:.3f}s")

    utilization = dashboard.get_worker_utilization()
    avg_util = sum(utilization.values()) / len(utilization)
    print(f"\nAverage utilization: {avg_util*100:.1f}%")

asyncio.run(main())
```

## Best Practices

### For Live Dashboards

1. **Use PipelineDashboard** for combining queries and events
2. **Send initial snapshot** when client connects
3. **Stream incremental updates** via events
4. **Poll infrequently** (1-2 seconds) for non-critical metrics
5. **Limit event subscribers** to avoid performance impact

### For Logging/Monitoring

1. **Query metrics at end** of pipeline run for summaries
2. **Use StatusTracker events** for real-time alerts
3. **Track worker utilization** to identify bottlenecks
4. **Monitor queue sizes** for backpressure detection

### Performance Considerations

- **Queries are cheap**: O(1) dict lookups
- **Snapshots copy data**: Use sparingly for large worker counts
- **Events are async**: Won't slow down pipeline
- **Automatic monitoring**: Minimal overhead (<1% typically)

## API Reference

See the [API documentation](../api/index.md) for complete details on:

- `Pipeline.get_worker_states()`
- `Pipeline.get_worker_metrics()`
- `Pipeline.get_dashboard_snapshot()`
- `PipelineDashboard`
- `WorkerState`
- `WorkerMetrics`
- `DashboardSnapshot`
