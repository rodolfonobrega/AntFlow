# Pipeline Guide

The `Pipeline` class enables multi-stage async processing with configurable worker pools, retry strategies, and real-time status tracking.

## Core Concepts

### Stages

A **Stage** represents a processing step with:
- One or more sequential tasks
- A pool of workers executing in parallel
- A retry strategy (per-task or per-stage)
- Automatic status tracking when StatusTracker is configured

### Pipeline

A **Pipeline** connects multiple stages together:
- Items flow from one stage to the next
- Each stage has its own queue and workers
- Order can be preserved across stages
- Results are collected from the final stage

## Basic Usage

### Creating a Simple Pipeline

```python
from antflow import Pipeline, Stage

async def fetch(x):
    return f"data_{x}"

async def process(x):
    return x.upper()

# Define stages
fetch_stage = Stage(name="Fetch", workers=3, tasks=[fetch])
process_stage = Stage(name="Process", workers=2, tasks=[process])

# Create pipeline
pipeline = Pipeline(stages=[fetch_stage, process_stage])

# Run pipeline
results = await pipeline.run(range(10))
```

### Multiple Tasks per Stage

A stage can have multiple tasks that execute sequentially for each item:

```python
import asyncio
from antflow import Pipeline, Stage

async def validate(x):
    if x < 0:
        raise ValueError("Negative value")
    return x

async def transform(x):
    return x * 2

async def format_output(x):
    return f"Result: {x}"

stage = Stage(
    name="ProcessStage",
    workers=3,
    tasks=[validate, transform, format_output]
)

pipeline = Pipeline(stages=[stage])
results = await pipeline.run(range(10))
```

## Retry Strategies

### Per-Task Retry

Each task retries independently using tenacity:

```python
from antflow import Stage

stage = Stage(
    name="FetchStage",
    workers=5,
    tasks=[fetch_from_api],
    retry="per_task",
    task_attempts=3,
    task_wait_seconds=1.0
)
```

- **`task_attempts`**: Maximum retry attempts per task
- **`task_wait_seconds`**: Wait time between retries

If a task fails after all retries, the stage fails for that item.

### Per-Stage Retry

The entire stage (all tasks) retries on any failure:

```python
from antflow import Stage

stage = Stage(
    name="TransactionStage",
    workers=2,
    tasks=[begin_transaction, update_db, commit],
    retry="per_stage",
    stage_attempts=3
)
```

- **`stage_attempts`**: Maximum retry attempts for the entire stage

If any task fails, the item is re-queued at the beginning of the stage.

### When to Use Which

**Per-Task Retry**:
- Independent tasks that can fail separately
- Fine-grained retry control
- Tasks with different failure modes

**Per-Stage Retry**:
- Transactional operations
- Tasks with dependencies
- All-or-nothing processing

## Status Tracking

Track items in real-time as they flow through the pipeline with `StatusTracker`.

### Basic Status Tracking

```python
from antflow import Pipeline, Stage, StatusTracker

tracker = StatusTracker()

stage = Stage(
    name="ProcessStage",
    workers=3,
    tasks=[my_task]
)

pipeline = Pipeline(stages=[stage], status_tracker=tracker)
results = await pipeline.run(items)

# Query statistics
stats = tracker.get_stats()
print(f"Completed: {stats['completed']}")
print(f"Failed: {stats['failed']}")
```

### Real-Time Event Monitoring

Get notified when items change status:

```python
from antflow import Pipeline, StatusTracker

async def on_status_change(event):
    print(f"{event.status.upper()}: Item {event.item_id} @ {event.stage}")

    if event.status == "failed":
        print(f"  Error: {event.metadata.get('error')}")
    elif event.status == "in_progress":
        print(f"  Worker: {event.worker}")

tracker = StatusTracker(on_status_change=on_status_change)
pipeline = Pipeline(stages=[stage], status_tracker=tracker)
```

### Task-Level Event Monitoring

For granular tracking, monitor individual tasks within stages:

```python
from antflow import StatusTracker, TaskEvent

async def on_task_retry(event: TaskEvent):
    print(f"⚠️  Task {event.task_name} retry #{event.attempt}")
    print(f"   Item: {event.item_id}, Error: {event.error}")

async def on_task_fail(event: TaskEvent):
    print(f"❌ Task {event.task_name} FAILED after {event.attempt} attempts")

    if event.task_name == "save_to_database":
        await send_critical_alert(f"Database save failed for {event.item_id}")

tracker = StatusTracker(
    # Limit specific tasks (e.g., API calls) to avoid rate limits
    task_concurrency_limits={
        "fetch_data": 5,  # Max 5 concurrent fetch_data calls
        "process_data": 20 # Max 20 concurrent process_data calls
    },
    on_success=handle_success,
    on_failure=handle_failure
)

### Task Concurrency Limits

You can limit the concurrency of specific tasks within a stage using `task_concurrency_limits`. This is useful when you have a high number of workers (e.g., 50) but one specific task (like an API call) has a strict rate limit (e.g., 5 concurrent requests).

- The limit applies **per task function name**.
- Workers that cannot acquire a semaphore for the task will wait, freeing up resources if they were in an async wait state (though in the current implementation, they block the worker slot until the semaphore is acquired).
- This ensures you don't exceed external system limits while keeping high throughput for other tasks.
stage = Stage(
    name="ETL",
    tasks=[extract, transform, validate, save],  # Multiple tasks
    retry="per_task",
    task_attempts=3
)

pipeline = Pipeline(stages=[stage], status_tracker=tracker)
```

**Task Events Available:**

- `on_task_start`: Called when a task begins execution
- `on_task_complete`: Called when a task completes successfully
- `on_task_retry`: Called when a task is retrying after a failure
- `on_task_fail`: Called when a task fails after all retry attempts

Each `TaskEvent` contains:
- `item_id`: Item being processed
- `stage`: Stage name
- `task_name`: Specific task function name
- `worker`: Worker processing the task
- `event_type`: "start", "complete", "retry", or "fail"
- `attempt`: Current attempt number (1-indexed)
- `timestamp`: When the event occurred
- `error`: Exception if task failed (None otherwise)
- `duration`: Task execution time in seconds (None for start events)

### Query Item Status

```python
# Get specific item status
status = tracker.get_status(item_id=42)
print(f"Item 42: {status.status} @ {status.stage}")

# Get all failed items
failed = tracker.get_by_status("failed")
for event in failed:
    print(f"Item {event.item_id}: {event.metadata['error']}")

# Get item history
history = tracker.get_history(item_id=42)
for event in history:
    print(f"{event.timestamp}: {event.status}")
```

### Status Types

Items progress through these states:
- `queued` - Waiting in stage queue
- `in_progress` - Being processed by worker
- `completed` - Successfully finished stage
- `failed` - Failed to complete stage

**Important:** Status tracking is at the **stage level**, not individual task level. If a stage has multiple tasks (e.g., `[validate, transform, enrich]`), you will know the stage failed but not which specific task caused the failure. The error message in `event.metadata['error']` will contain details about the failure. For task-level granularity, consider using separate stages (one task per stage) or adding logging within tasks.

## Order Preservation

Results are always returned in input order:

```python
from antflow import Pipeline

pipeline = Pipeline(stages=[stage1, stage2])
results = await pipeline.run(items)
# Results maintain input order
```



## Monitoring Strategies

AntFlow supports two primary ways to monitor your pipeline: **Event-Driven (Callbacks)** and **Polling**.

### Strategy 1: Event-Driven (Callbacks)

Use `StatusTracker` callbacks to react immediately when events occur. This is best for:
- Real-time dashboards (low latency)
- Logging specific events (e.g., errors)
- Triggering external actions (e.g., alerts)

**Example:** `examples/rich_callback_dashboard.py` demonstrates this approach.

```python
async def on_status_change(event):
    # React immediately to status changes
    print(f"Item {event.item_id} is now {event.status}")

tracker = StatusTracker(on_status_change=on_status_change)
pipeline = Pipeline(stages=[...], status_tracker=tracker)
await pipeline.run(items)
```

### Strategy 2: Polling (Loop)

Run a separate loop to periodically check `pipeline.get_stats()` or `pipeline.get_dashboard_snapshot()`. This is best for:
- Periodic metrics aggregation
- Decoupled monitoring (UI runs at its own FPS)
- Reducing overhead (batching updates)

**Example:** `examples/rich_polling_dashboard.py` demonstrates this approach.

```python
async def monitor_loop(pipeline):
    while True:
        # Poll current state every second
        stats = pipeline.get_stats()
        print(f"Processed: {stats.items_processed}, In-Flight: {stats.items_in_flight}")
        await asyncio.sleep(1.0)

async with asyncio.TaskGroup() as tg:
    tg.create_task(monitor_loop(pipeline))
    await pipeline.run(items)
```

## Feeding Data

### Synchronous Iterable

```python
items = list(range(100))
results = await pipeline.run(items)
```

### Async Iterable

```python
import asyncio

async def data_generator():
    for i in range(100):
        await asyncio.sleep(0.01)
        yield i

await pipeline.feed_async(data_generator())
```

### Dict Input

Pass dict items with custom IDs:

```python
items = [
    {"id": "user_1", "value": {"name": "Alice"}},
    {"id": "user_2", "value": {"name": "Bob"}},
]
results = await pipeline.run(items)
```

## Context Manager

Use pipeline as a context manager for automatic cleanup:

```python
from antflow import Pipeline

async with Pipeline(stages=[stage1, stage2]) as pipeline:
    results = await pipeline.run(items)
# Pipeline is automatically shut down
```

## Error Handling

### Tracking Failures with StatusTracker

```python
from antflow import Pipeline, Stage, StatusTracker

tracker = StatusTracker()

stage = Stage(
    name="RiskyStage",
    workers=3,
    tasks=[risky_task],
    retry="per_task",
    task_attempts=3
)

pipeline = Pipeline(stages=[stage], status_tracker=tracker)
results = await pipeline.run(items)

# Get statistics
stats = tracker.get_stats()
print(f"Succeeded: {stats['completed']}")
print(f"Failed: {stats['failed']}")

# Get failed items
failed_items = tracker.get_by_status("failed")
for event in failed_items:
    print(f"Item {event.item_id}: {event.metadata['error']}")
```

### Extracting Error Information

Errors are available in the event metadata:

```python
from antflow import StatusTracker

async def on_status_change(event):
    if event.status == "failed":
        error = event.metadata.get('error')
        print(f"Item {event.item_id} failed: {error}")

tracker = StatusTracker(on_status_change=on_status_change)
```

## Worker-Level Tracking

Each worker has a unique ID (0 to N-1). Track which worker processes which item:

```python
from antflow import Pipeline, StatusTracker

async def on_status_change(event):
    if event.status == "in_progress":
        print(f"Worker {event.worker_id}: processing {event.item_id}")
    elif event.status == "completed":
        print(f"Worker {event.worker_id}: completed {event.item_id}")

tracker = StatusTracker(on_status_change=on_status_change)
pipeline = Pipeline(stages=[stage], status_tracker=tracker)

worker_names = pipeline.get_worker_names()
```

See the [Worker Tracking Guide](worker-tracking.md) for detailed examples including:

- Custom item IDs for better tracking
- Worker utilization analysis
- Load balancing monitoring
- Error tracking by worker

## Complete ETL Example

```python
import asyncio
from antflow import Pipeline, Stage

class ETLProcessor:
    async def extract(self, item_id):
        # Fetch from API/database
        await asyncio.sleep(0.1)
        return {"id": item_id, "data": f"raw_{item_id}"}

    async def validate(self, data):
        # Validate data
        if "data" not in data:
            raise ValueError("Invalid data")
        return data

    async def transform(self, data):
        # Transform data
        data["processed"] = data["data"].upper()
        return data

    async def enrich(self, data):
        # Enrich with additional data
        data["metadata"] = {"timestamp": "2025-10-09"}
        return data

    async def load(self, data):
        # Save to database
        await asyncio.sleep(0.1)
        data["saved"] = True
        return data

async def main():
    processor = ETLProcessor()

    # Extract stage with high concurrency
    extract_stage = Stage(
        name="Extract",
        workers=10,
        tasks=[processor.extract],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=2.0
    )

    # Transform stage with validation
    transform_stage = Stage(
        name="Transform",
        workers=5,
        tasks=[processor.validate, processor.transform, processor.enrich],
        retry="per_stage",  # Transactional
        stage_attempts=3
    )

    # Load stage with retries
    load_stage = Stage(
        name="Load",
        workers=3,
        tasks=[processor.load],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=3.0
    )

    # Build pipeline
    pipeline = Pipeline(
        stages=[extract_stage, transform_stage, load_stage]
    )

    # Process items
    item_ids = range(100)
    results = await pipeline.run(item_ids)

    print(f"Processed {len(results)} items")
    print(f"Stats: {pipeline.get_stats()}")

asyncio.run(main())
```

## Best Practices

### Worker Pool Sizing

- **Extract/Fetch**: More workers (I/O-bound)
- **Transform**: Moderate workers (CPU-bound)
- **Load/Save**: Fewer workers (rate-limited)

### Retry Configuration

- Use **per-task** for independent operations
- Use **per-stage** for transactional operations
- Set appropriate `task_wait_seconds` for rate limiting
- Increase `task_attempts` for flaky external services

### Callbacks

- Use callbacks for logging and monitoring
- Keep callbacks lightweight (use queues for heavy operations)
- Avoid long-running operations in callbacks

### Error Handling

- Always set up `on_failure` callbacks for production
- Log failed items for later retry/analysis
- Monitor `items_failed` metric
