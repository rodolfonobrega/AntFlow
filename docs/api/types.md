# Types API

The `antflow.types` module defines the core data structures used for type hinting and data exchange between components.

## Overview

This module contains Data Classes that represent the state of the system, including events, metrics, and snapshots.





## Enumerated Types

### StatusType

Represents the current state of an item in the pipeline.

| Value | Description |
|-------|-------------|
| `queued` | Item is waiting in a stage's input queue. |
| `in_progress` | Item is currently being processed by a worker. |
| `completed` | Item has successfully finished processing in the stage. |
| `failed` | Item failed processing (after exhausting retries). |
| `retrying` | Item failed but is queued for a retry (per-stage retry strategy). |

### WorkerStatus

Represents the current activity state of a worker.

| Value | Description |
|-------|-------------|
| `idle` | Worker is waiting for new items. |
| `busy` | Worker is currently processing an item. |

### TaskEventType

Represents the type of event occurring at the task level.

| Value | Description |
|-------|-------------|
| `start` | A task function has started execution. |
| `complete` | A task function has completed successfully. |
| `retry` | A task failed and is being retried. |
| `fail` | A task failed permanently (after exhausting retries). |

## Data Classes

::: antflow.types
    options:
      show_root_heading: false
      show_source: false
      members_order: source
