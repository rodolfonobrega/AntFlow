# StatusTracker API

The `antflow.tracker` module provides real-time monitoring and event tracking for pipelines.

## Overview

The **[StatusTracker][antflow.tracker.StatusTracker]** allows you to observe items as they move through the pipeline. It captures events like:

- Item queued
- Processing started
- Task completion
- Retries
- Failures

You can use it to build dashboards, progress bars, or simply to log the state of your processing.

## Usage Example

```python
from antflow import Pipeline, Stage, StatusTracker

# 1. Create a tracker
tracker = StatusTracker()

# 2. Attach to pipeline
pipeline = Pipeline(
    stages=[...],
    status_tracker=tracker
)

# 3. Run pipeline
await pipeline.run(items)

# 4. Query status
stats = tracker.get_stats()
print(f"Completed: {stats['completed']}")

# 5. Get history for a specific item
history = tracker.get_history(item_id=123)
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
