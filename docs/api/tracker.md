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

## Available Callbacks

You can provide these async callbacks to the `StatusTracker` constructor to react to specific events:

| Callback | Signature | Description |
|----------|-----------|-------------|
| `on_status_change` | `async def fn(event: StatusEvent)` | Triggered when an item's status changes (queued, in_progress, completed, failed). |
| `on_task_start` | `async def fn(event: TaskEvent)` | Triggered when a specific task function starts execution. |
| `on_task_complete` | `async def fn(event: TaskEvent)` | Triggered when a task function completes successfully. |
| `on_task_retry` | `async def fn(event: TaskEvent)` | Triggered when a task fails but will be retried. |
| `on_task_fail` | `async def fn(event: TaskEvent)` | Triggered when a task fails permanently (after all retries). |

## Event Objects Structure

When using callbacks, you will receive either a `StatusEvent` or a `TaskEvent`. Here are their properties:

### StatusEvent Properties
| Property | Type | Description |
|----------|------|-------------|
| `item_id` | `Any` | Unique identifier for the item. |
| `stage` | `str` | Name of the stage where the event occurred. |
| `status` | `str` | Current status (`queued`, `in_progress`, `completed`, `failed`). |
| `worker` | `str` | Name of the worker (e.g., `Fetch-W0`). |
| `timestamp` | `float` | Unix timestamp of the event. |
| `metadata` | `dict` | Additional context (e.g., error details). |
| `worker_id` | `int` | Helper to get the worker index (e.g., `0` from `Fetch-W0`). |

### TaskEvent Properties
| Property | Type | Description |
|----------|------|-------------|
| `item_id` | `Any` | Unique identifier for the item. |
| `stage` | `str` | Name of the stage. |
| `task_name` | `str` | Name of the specific task function. |
| `worker` | `str` | Name of the worker processing the task. |
| `event_type` | `str` | Type of event (`start`, `complete`, `retry`, `fail`). |
| `attempt` | `int` | Current attempt number (1-indexed). |
| `timestamp` | `float` | Unix timestamp of the event. |
| `error` | `Exception` | Exception object if task failed or is retrying. |
| `duration` | `float` | Time taken to execute (seconds), if completed/failed. |

## Event Types

For quick reference, here are the possible values for status and event types:

### Item Status (`StatusEvent.status`)
| Value | Description |
|-------|-------------|
| `queued` | Item has been added to a stage's input queue. |
| `in_progress` | Worker has picked up the item and started processing. |
| `completed` | All tasks in the stage finished successfully. |
| `failed` | Stage execution failed (after all retries). |

### Task Events (`TaskEvent.event_type`)
| Value | Description |
|-------|-------------|
| `start` | A specific task function started running. |
| `complete` | Task function returned successfully. |
| `retry` | Task failed but has retries remaining. |
| `fail` | Task failed and has no retries left. |

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
