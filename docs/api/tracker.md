# StatusTracker API

The `antflow.tracker` module provides real-time monitoring and event tracking for pipelines.

## Overview

The **[StatusTracker][antflow.tracker.StatusTracker]** is the observability layer of AntFlow. It allows you to:
1.  **Monitor Items**: Track the lifecycle of data items as they move through stages.
2.  **Monitor Tasks**: Get granular events for every task execution (start, success, retry, failure).
3.  **Build Dashboards**: Use the event stream to power real-time UIs.

## Usage Example

```python
from antflow import Pipeline, Stage, StatusTracker

# 1. Define a custom handler
async def on_event(event):
    if event.status == "failed":
        print(f"🚨 Alert: Item {event.item_id} failed in {event.stage}")

# 2. Initialize tracker
tracker = StatusTracker(on_status_change=on_event)

# 3. Attach to pipeline
pipeline = Pipeline(stages=[...], status_tracker=tracker)

# 4. Run
await pipeline.run(items)
```



## Customizing Behavior

You can customize how status changes are handled by providing callbacks or subclassing `StatusTracker`.

### Using Callbacks

The easiest way to react to events is by passing async callbacks during initialization:

```python
async def on_fail(event: TaskEvent):
    # Send alert to Slack/Discord
    await send_alert(f"Item {event.item_id} failed: {event.error}")

tracker = StatusTracker(
    on_task_fail=on_fail,
    on_status_change=lambda e: print(f"Status: {e.status}")
)
```

### Accessing Worker & Job Status

The `StatusTracker` focuses on **Item** progress. To monitor **Workers**, use the `Pipeline` methods:

```python
# Item Status (via Tracker)
item_status = tracker.get_status(item_id=123)

# Worker Status (via Pipeline)
worker_states = pipeline.get_worker_states()
for name, state in worker_states.items():
    print(f"Worker {name}: {state.status}")
```

## Class Reference

### StatusEvent

::: antflow.tracker.StatusEvent
    options:
      show_root_heading: true
      show_source: false
      members_order: source

### StatusTracker

::: antflow.tracker.StatusTracker
    options:
      show_root_heading: true
      show_source: false
      members_order: source
