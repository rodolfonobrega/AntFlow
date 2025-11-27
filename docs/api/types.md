# Types API

The `antflow.types` module defines the core data structures used for type hinting and data exchange between components.

## Overview

This module contains Data Classes that represent the state of the system, including events, metrics, and snapshots.

## Core Types

### TaskEvent

Represents a granular event occurring within a task execution.

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | `Any` | The identifier of the item being processed. |
| `stage` | `str` | Name of the stage where the event occurred. |
| `task_name` | `str` | Name of the specific task function. |
| `worker` | `str` | Name of the worker processing the task. |
| `event_type` | `Literal` | One of: `"start"`, `"complete"`, `"retry"`, `"fail"`. |
| `attempt` | `int` | Current attempt number (1-indexed). |
| `timestamp` | `float` | Unix timestamp of the event. |
| `error` | `Exception` | The exception raised (if any). |
| `duration` | `float` | Execution duration in seconds (for completion events). |

### WorkerMetrics

Tracks performance metrics for a single worker.

| Field | Type | Description |
|-------|------|-------------|
| `worker_name` | `str` | Unique name of the worker (e.g., "Stage1-W0"). |
| `stage` | `str` | Name of the stage the worker belongs to. |
| `items_processed` | `int` | Total number of items successfully processed. |
| `items_failed` | `int` | Total number of items that failed. |
| `total_processing_time` | `float` | Cumulative processing time in seconds. |
| `last_active` | `float` | Timestamp of the last activity. |

### PipelineStats

Aggregated statistics for the entire pipeline.

| Field | Type | Description |
|-------|------|-------------|
| `items_processed` | `int` | Total items fully processed by the pipeline. |
| `items_failed` | `int` | Total items that failed in the pipeline. |
| `items_in_flight` | `int` | Number of items currently in queues or being processed. |
| `queue_sizes` | `Dict[str, int]` | Mapping of stage names to current queue sizes. |

## Type Reference

::: antflow.types
    options:
      show_root_heading: false
      show_source: false
      members_order: source
