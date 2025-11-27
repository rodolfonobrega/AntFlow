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

## Event Reference

### Item Status Events (`StatusEvent`)

These events represent the high-level state of an item within a stage.

| Status | Triggered When | Metadata |
|--------|----------------|----------|
| `queued` | Item enters a stage's input queue. | `{"attempt": int, "retry": bool}` (if retrying) |
| `in_progress` | Worker picks up item and starts processing. | None |
| `completed` | All tasks in the stage finished successfully. | None |
| `failed` | Stage execution failed (after all retries). | `{"error": str}` |

### Task Execution Events (`TaskEvent`)

These events represent the execution of individual functions *within* a stage.

| Event Type | Triggered When | Metadata/Attributes |
|------------|----------------|---------------------|
| `start` | A specific task function starts running. | `attempt` (int) |
| `complete` | Task function returns successfully. | `duration` (float) |
| `retry` | Task failed but has retries remaining. | `error` (Exception), `attempt` (int) |
| `fail` | Task failed and has no retries left. | `error` (Exception) |

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
