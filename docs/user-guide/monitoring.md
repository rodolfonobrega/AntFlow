# Monitoring: Dashboard vs StatusTracker

AntFlow provides two primary mechanisms for monitoring pipeline execution. Understanding the differences between them will help you choose the right tool for your use case.

## Overview

| Feature | Dashboard | StatusTracker |
|---------|-----------|---------------|
| **Mechanism** | Polling (periodic updates) | Event-driven (callbacks) |
| **Use Case** | Visual monitoring, progress display | Logging, system integration, debugging |
| **Performance** | Low overhead, updates every N seconds | Immediate updates on every event |
| **Complexity** | Simple (built-in dashboards) | Flexible (custom callbacks) |
| **Data Access** | Current state snapshots | Complete event history |

## Dashboard: Polling-based Monitoring

### How It Works

Dashboard uses a **polling** mechanism where a background task periodically queries the pipeline state:
1. Background task calls `get_dashboard_snapshot()` every N seconds (default 0.5)
2. Snapshot contains current worker states, metrics, and pipeline statistics
3. Dashboard renders the snapshot to the terminal or custom UI

### Built-in Dashboards

AntFlow includes three built-in dashboards:

```python
from antflow import Pipeline, Stage

async def task(x):
    await asyncio.sleep(0.1)
    return x * 2

pipeline = Pipeline(stages=[Stage(name="Process", workers=5, tasks=[task])])

# Option 1: Minimal progress bar
await pipeline.run(items, progress=True)

# Option 2: Compact dashboard
await pipeline.run(items, dashboard="compact")

# Option 3: Detailed dashboard (shows per-stage progress)
await pipeline.run(items, dashboard="detailed")

# Option 4: Full dashboard (includes error summary)
await pipeline.run(items, dashboard="full")
```

### When to Use Dashboard

✅ **Perfect for:**
- Interactive development and debugging
- Real-time progress visualization
- Identifying bottlenecks in multi-stage pipelines
- Monitoring during production runs

❌ **Not ideal for:**
- Storing events in external systems (databases, logs)
- Complex business logic based on specific events
- High-frequency event processing (>10 events/second)

### Performance Considerations

The polling interval is configurable:

```python
# Fast updates (more responsive, higher CPU)
await pipeline.run(items, dashboard="detailed", dashboard_update_interval=0.1)

# Slow updates (less responsive, lower CPU)
await pipeline.run(items, dashboard="detailed", dashboard_update_interval=1.0)
```

**Recommended range:** 0.1 to 1.0 seconds.

### Custom Dashboards

You can create custom dashboards using the `DashboardProtocol`:

```python
from antflow import Pipeline, PipelineResult, DashboardSnapshot, DashboardProtocol

class MyDashboard(DashboardProtocol):
    def on_start(self, pipeline, total_items):
        self.total = total_items
        print(f"Starting to process {total_items} items...")

    def on_update(self, snapshot: DashboardSnapshot):
        stats = snapshot.pipeline_stats
        progress = (stats.items_processed / self.total) * 100
        print(f"Progress: {progress:.1f}% ({stats.items_processed}/{self.total})")

    def on_finish(self, results: list[PipelineResult], summary):
        print(f"Done! Processed {len(results)} items")
        if summary.total_failed > 0:
            print(f"Failed: {summary.total_failed}")

# Use custom dashboard
pipeline = Pipeline(stages=[...])
await pipeline.run(items, custom_dashboard=MyDashboard())
```

## StatusTracker: Event-driven Monitoring

### How It Works

StatusTracker uses **async callbacks** that are invoked immediately when events occur:
1. Pipeline emits events (queued, in_progress, completed, failed, etc.)
2. StatusTracker invokes registered callbacks
3. Callbacks can log, store, or process events immediately

### Basic Usage

```python
from antflow import Pipeline, StatusTracker, StatusEvent

async def on_status_change(event: StatusEvent):
    print(f"Item {event.item_id}: {event.status} @ {event.stage}")

tracker = StatusTracker(on_status_change=on_status_change)

pipeline = Pipeline(stages=[...], status_tracker=tracker)
await pipeline.run(items)
```

### Event Types

StatusTracker can track multiple types of events:

```python
async def on_queued(event: StatusEvent):
    print(f"Queued: {event.item_id}")

async def on_start(event: StatusEvent):
    print(f"Started: {event.item_id} on worker {event.worker}")

async def on_completed(event: StatusEvent):
    print(f"Completed: {event.item_id}")

async def on_failed(event: StatusEvent):
    error = event.metadata.get("error", "Unknown")
    print(f"Failed: {event.item_id} - {error}")

tracker = StatusTracker(
    on_status_change=on_queued,  # Called for ALL status changes
)
# Or use specific callbacks:
# tracker = StatusTracker(
#     on_status_change=lambda e: print(f"Status: {e.status}"),
#     on_task_start=lambda e: print(f"Task started: {e.task_name}"),
#     on_task_complete=lambda e: print(f"Task done: {e.task_name}"),
#     on_task_retry=lambda e: print(f"Retrying: {e.task_name}"),
#     on_task_fail=lambda e: print(f"Task failed: {e.task_name}"),
# )
```

### Querying StatusTracker

After execution, you can query the tracker for information:

```python
# Get current status of an item
status = tracker.get_status(item_id=42)
print(f"Current status: {status.status}")

# Get all items in a specific status
failed_items = tracker.get_by_status("failed")
for item in failed_items:
    print(f"Failed item: {item.item_id}")

# Get aggregate statistics
stats = tracker.get_stats()
print(f"Completed: {stats['completed']}, Failed: {stats['failed']}")

# Get complete event history for an item
history = tracker.get_history(item_id=42)
for event in history:
    print(f"{event.timestamp}: {event.status} @ {event.stage}")
```

### Error Summary

StatusTracker provides aggregated error information:

```python
error_summary = tracker.get_error_summary()
print(f"Total failed: {error_summary.total_failed}")

# Group by error type
for error_type, count in error_summary.errors_by_type.items():
    print(f"  {error_type}: {count}")

# Group by stage
for stage, count in error_summary.errors_by_stage.items():
    print(f"  {stage}: {count}")

# Get individual failed items
for failed_item in error_summary.failed_items:
    print(f"Item {failed_item.item_id}: {failed_item.error}")
```

### When to Use StatusTracker

✅ **Perfect for:**
- Logging events to external systems (databases, log files)
- Integrating with monitoring tools (Prometheus, DataDog, etc.)
- Implementing custom business logic based on events
- Debugging complex failure scenarios
- Storing complete event history for audit trails

❌ **Not ideal for:**
- Simple progress visualization (use Dashboard instead)
- Real-time terminal output (use built-in dashboards)
- Cases where you only need aggregate statistics (use `get_stats()`)

### Task-Level Events

StatusTracker also tracks events at the task level (within a stage):

```python
async def on_task_start(event):
    print(f"Task '{event.task_name}' started on {event.worker}")

async def on_task_complete(event):
    duration = event.duration
    print(f"Task '{event.task_name}' completed in {duration:.2f}s")

async def on_task_retry(event):
    print(f"Task '{event.task_name}' retrying (attempt {event.attempt})")

async def on_task_fail(event):
    print(f"Task '{event.task_name}' failed: {event.error}")

tracker = StatusTracker(
    on_task_start=on_task_start,
    on_task_complete=on_task_complete,
    on_task_retry=on_task_retry,
    on_task_fail=on_task_fail,
)
```

## Combining Both Mechanisms

You can use Dashboard and StatusTracker together:

```python
from antflow import Pipeline, StatusTracker

async def log_to_db(event):
    # Store event in database
    await db.insert(event)

tracker = StatusTracker(on_status_change=log_to_db)

pipeline = Pipeline(
    stages=[...],
    status_tracker=tracker,
)

# Use dashboard for visual monitoring + tracker for logging
await pipeline.run(items, dashboard="detailed")
```

This gives you:
- **Visual feedback** in the terminal (Dashboard)
- **Persistent logging** to external systems (StatusTracker)
- **Complete event history** for debugging (StatusTracker)

## Performance Comparison

| Metric | Dashboard | StatusTracker |
|--------|-----------|---------------|
| **CPU overhead** | Low (one snapshot every N seconds) | Medium (callback per event) |
| **Memory usage** | Low (only current state) | Medium (stores event history) |
| **Latency** | Up to N seconds | Immediate |
| **Scalability** | Good for any scale | Depends on callback complexity |

## Choosing the Right Tool

### Use Dashboard when:
- You need visual progress feedback
- You're debugging in an interactive terminal
- You want to identify bottlenecks quickly
- You don't need to store event history

### Use StatusTracker when:
- You need to log events to external systems
- You want complete event history for debugging
- You need to implement custom business logic
- You're integrating with monitoring tools

### Use Both when:
- You want visual feedback AND persistent logging
- You're debugging in production and need both views
- You need to show progress to users while logging internally

## Examples

See the [examples](../examples/) directory for complete working examples:

- [monitoring_status_tracker.py](../examples/monitoring_status_tracker.py) - StatusTracker with callbacks
- [dashboard_levels.py](../examples/dashboard_levels.py) - Using different dashboard levels
- [custom_dashboard_callbacks.py](../examples/custom_dashboard_callbacks.py) - Custom dashboard with tracker
- [monitoring_workers.py](../examples/monitoring_workers.py) - Worker-level monitoring
