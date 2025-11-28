# Types API

The `antflow.types` module defines the core data structures used for type hinting and data exchange between components.

## Overview

This module contains Data Classes that represent the state of the system, including events, metrics, and snapshots.



## Event Objects

AntFlow uses event objects to track the state of items and tasks.

### StatusEvent
Represents a change in the high-level status of an item (e.g., entering a stage, completing processing).

| Property | Type | Description |
|----------|------|-------------|
| `item_id` | `Any` | Unique identifier for the item. |
| `stage` | `str` | Name of the stage where the event occurred. |
| `status` | `str` | Current status (`queued`, `in_progress`, `completed`, `failed`). |
| `worker` | `str` | Name of the worker (e.g., `Fetch-W0`). |
| `timestamp` | `float` | Unix timestamp of the event. |
| `metadata` | `dict` | Additional context (e.g., error details). |
| `worker_id` | `int` | Helper to get the worker index (e.g., `0` from `Fetch-W0`). |

### TaskEvent
Represents a granular event during the execution of a specific task function.

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

## Type Reference

::: antflow.types
    options:
      show_root_heading: false
      show_source: false
      members_order: source
