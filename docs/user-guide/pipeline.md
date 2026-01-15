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


## Creating Pipelines (Three Approaches)

AntFlow offers three equivalent ways to create pipelines depending on your needs.

### 1. Fluent Builder API (Concise & Recommended)

Use `Pipeline.create()` for a clean, chainable builder pattern. This is ideal for most multi-stage pipelines.

```python
from antflow import Pipeline

async def main():
    results = await (
        Pipeline.create()
        .add("Fetch", fetch_task, workers=10)
        .add("Process", process_task, workers=5)
        .run(items, progress=True)
    )
```

### 2. Manual Stage Construction (Full Control)

Explicitly define `Stage` objects. Use this when you need fine-grained control over advanced parameters like `task_concurrency_limits` or `skip_if`.

```python
from antflow import Pipeline, Stage

stage1 = Stage(name="Fetch", workers=10, tasks=[fetch_task])
stage2 = Stage(name="Process", workers=5, tasks=[process_task])

pipeline = Pipeline(stages=[stage1, stage2])
results = await pipeline.run(items)
```

### 3. Quick One-Liner API

For simple scripts or single-stage processing, use `Pipeline.quick()`.

```python
from antflow import Pipeline

# Single task
results = await Pipeline.quick(items, process_task, workers=5, progress=True)

# Multiple tasks in one stage
results = await Pipeline.quick(items, [fetch, process], workers=10)
```

| Method | When to Use |
|--------|-------------|
| **Fluent API** | Multi-stage pipelines, clean code, prototyping |
| **Manual Stages** | Custom parameters, complex topologies, explicit configuration |
| **Pipeline.quick()** | Single-stage processing, simple scripts, one-off tasks |

---

## Stage Configuration Reference

The `Stage` class is the building block of your pipeline. Here are all the available configuration options:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`name`** | `str` | *Required* | Unique identifier for the stage. Used in logs and status events. |
| **`workers`** | `int` | *Required* | Number of concurrent workers for this stage. |
| **`tasks`** | `List[TaskFunc]` | *Required* | List of async functions to execute sequentially for each item. |
| **`retry`** | `str` | `"per_task"` | Retry strategy: `"per_task"` (retry individual function) or `"per_stage"` (restart stage from first task). |
| **`task_attempts`** | `int` | `3` | Max attempts per task (used in `"per_task"` mode). |
| **`stage_attempts`** | `int` | `3` | Max attempts per stage (used in `"per_stage"` mode). |
| **`task_wait_seconds`** | `float` | `1.0` | Time to wait between retries. |
| **`task_concurrency_limits`** | `Dict[str, int]` | `None` | Max concurrent executions for specific task functions (see example below). |
| **`unpack_args`** | `bool` | `False` | If `True`, unpacks the input item (`*args`/`**kwargs`) when calling the first task. |
| **`on_success`** | `Callable` | `None` | Callback or `async` function to run on successful item completion. |
| **`on_failure`** | `Callable` | `None` | Callback or `async` function to run on item failure (after all retries). |
| **`skip_if`** | `Callable` | `None` | Predicate function `(item) -> bool`. If `True`, the item skips this stage entirely. |
| **`queue_capacity`** | `int` | `None` | Optional. Manually set input queue size. If `None` (default), uses smart limit (`workers * 10`). Set to `0` for infinite. |

### Use Case: OpenAI Batch Processing

`task_concurrency_limits` is powerful when you have a large worker pool for general processing but need to throttle specific operations (like API uploads) due to strict rate limits.

**Scenario:**
You have 1000 jobs to process using OpenAI's Batch API.
The process is: `Generate -> Upload -> Start Job -> Poll -> Download`.

**The Constraints:**

1.  **Strict Upload Limit:** You can only upload **2 files** at the same time (rate limit).
2.  **Batch Queue Capacity:** You can have **max 50 active jobs** running in the Batch API at once.

**The Problem:**
*   If you set `workers=2` (to satisfy the upload limit), you will only ever have 2 jobs running in the Batch API. You are wasting 48 slots of capacity!
*   If you set `workers=50` (to fill the Batch API capacity), all 50 workers will try to upload files simultaneously at the start, causing you to hit the upload rate limit and crash.

**Solution:**
Use `workers=50` to maximize your Batch API usage, but use `task_concurrency_limits` to throttle *only* the upload task to 2.

```python
import asyncio
from antflow import Stage, Pipeline

async def upload_file(item):
    await asyncio.sleep(0.1)
    return f"uploaded_{item}"

async def poll_status(item):
    await asyncio.sleep(0.1)
    return "done"

async def main():
    stage = Stage(
        name="OpenAI_Batch_Job",
        workers=50,
        tasks=[upload_file, poll_status],
        task_concurrency_limits={
            "upload_file": 2  # Limits concurrent uploads to 2
        }
    )
    pipeline = Pipeline(stages=[stage])
    await pipeline.run(range(10), progress=True)

if __name__ == "__main__":
    asyncio.run(main())
```

**Architecture Comparison: Two Stages vs. Single Stage**

Previously, users were forced to use a single stage with task limits to avoid the "firehose" effect. With the introduction of **Automatic Backpressure**, both approaches are now viable.

### Option A: Two Stages (Recommended for Clarity) ✅

```python
# ✅ Highly recommended: Separates concerns
stage_upload = Stage("Upload", workers=2, tasks=[upload])
stage_poll = Stage("Polling", workers=50, tasks=[poll], queue_capacity=5)
```

*   **Structure**: `UploadStage (2 workers)` -> `PollingStage (50 workers)`.
*   **Behavior**: `queue_capacity` is an **additional buffer** for items waiting to be picked up.
*   **The Math**: With 50 workers and a capacity of 5, the stage can hold **55 items** in total (50 being processed + 5 waiting in line).
*   **Backpressure**: Once item #56 arrives, the `UploadStage` will block until a poller finishes.
*   **Result**: Your 50 workers are **always busy** as long as there is work, but you have a strict cap on how many total jobs are "in flight" at the same time.

### Option B: Single Stage + Task Limits (Compact) ✅

```python
# ✅ Also works well
stage = Stage(
    "Combined", 
    workers=50, 
    tasks=[upload, poll],
    task_concurrency_limits={"upload": 2}
)
```

*   **Structure**: One Stage (50 workers total) with `limit={upload: 2}`.
*   **Behavior**: When all 50 workers are busy polling, no new upload tasks can start. 
*   **Total "Active" Jobs**: Strictly capped at 50.
*   **Result**: Fewer stages to manage. However, if all 50 workers are stuck polling, no one can start a new upload even if the rate limit allows it.

---

### The Danger: Life Without Backpressure (The "Firehose" Risk) ❌

To understand why backpressure matters, imagine we have **infinite queues** (which was the default before version 0.6.1).

**The Scenario:**
1.  **Stage A (Upload)** has 2 workers and takes 1 second per job.
2.  **Stage B (Polling)** has 50 workers but takes 10 minutes per job (waiting for OpenAI).
3.  **You feed 1000 items.**

**What happens without Backpressure?**
*   **Stage A** starts fast. Every 1 second, it finishes 2 uploads and pushes them to **Stage B**.
*   **Stage B** can only process 50 jobs at a time. The rest (950 jobs) sit in its queue.
*   **The Trap**: Since Stage A doesn't know Stage B is full, it keeps uploading. After a few minutes, Stage A has successfully uploaded **750 files**.
*   **The Disaster**: You now have **750 active jobs** on OpenAI, but you only have **50 workers** monitoring them. If jobs fail or finish, you won't know for a long time. You have effectively bypassed your own concurrency intent and might crash your OpenAI account limits or your local memory.

**This is a "Firehose"**: A fast stage drowning a slow stage because there is no way to say *"Stop, I'm full!"*.

---

### Automatic Backpressure (Smart Limits)

As of version 0.6.1, AntFlow implements **Smart Internal Limits** for all stage queues.

*   **How it works:** Each stage has a limited input queue size. The default limit is `max(1, workers * 10)`. 
*   **Example:** A stage with 5 workers allows ~50 items to be queued waiting for processing.
*   **Effect:** If a stage is slow, its input queue fills up. Once full, the **previous stage** (or the `feed()` call) is blocked from adding more items until space clears up.
*   **Benefit:** This automatically propagates backpressure upstream, preventing memory exhaustion and regulating flow without manual configuration.

**Customizing Limits:**

You can override this behavior using the `queue_capacity` parameter:

```python
stage = Stage(
    name="BufferStage",
    workers=2,
    queue_capacity=1000, # Large buffer
    tasks=[process]
)
```

## Basic Usage

### Creating a Simple Pipeline

```python
import asyncio
from antflow import Pipeline, Stage

async def fetch(x):
    await asyncio.sleep(0.1)
    return f"data_{x}"

async def main():
    stage = Stage(name="Fetch", workers=3, tasks=[fetch])
    pipeline = Pipeline(stages=[stage])
    results = await pipeline.run(range(10), progress=True)
    print(f"Results: {len(results)} items")

if __name__ == "__main__":
    asyncio.run(main())
```

### Interactive Execution

For more control, you can split execution into `start`, `feed`, and `join` steps. This allows you to inject items dynamically while the pipeline is running:

```python
# Start background workers
await pipeline.start()

# Feed initial batch to first stage (default)
await pipeline.feed(batch_1)

# Do other work...

# Inject items directly into a specific stage (e.g., resuming from a checkpoint)
# This item will skip previous stages and start processing at 'ProcessStage'
await pipeline.feed(recovered_items, target_stage="ProcessStage")

# Wait for completion
await pipeline.join()

# Access results
print(pipeline.results)
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
    on_success=handle_success,
    on_failure=handle_failure
)

### Task Concurrency Limits

You can limit the concurrency of specific tasks within a stage using `task_concurrency_limits`. This is useful when you have a high number of workers (e.g., 50) but one specific task (like an API call) has a strict rate limit (e.g., 5 concurrent requests).

See the [Concurrency Control Guide](concurrency.md) for more details.

```python
stage = Stage(
    name="ETL",
    tasks=[extract, transform, validate, save],
    retry="per_task",
    task_attempts=3,
    # Limit specific tasks (e.g., API calls) to avoid rate limits
    task_concurrency_limits={
        "extract": 5,  # Max 5 concurrent extract calls
        "save": 20     # Max 20 concurrent save calls
    }
)

pipeline = Pipeline(stages=[stage], status_tracker=tracker)
```
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
- `retrying` - Item is being retried after a failure
- `skipped` - Item was skipped via `skip_if` predicate

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

### Strategy 3: Programmatic Monitoring (get_stats)

For simple scripts that just need a summary after execution, or for background metrics collection, use `pipeline.get_stats()`. This returns a `PipelineStats` object containing high-level metrics and detailed `StageStats` for each stage.

```python
stats = pipeline.get_stats()

print(f"Total processed: {stats.items_processed}")
print(f"Total failed: {stats.items_failed}")

# Access per-stage metrics
for stage_name, stage_stat in stats.stage_stats.items():
    print(f"Stage {stage_name}:")
    print(f"  Completed: {stage_stat.completed_items}")
    print(f"  Failed: {stage_stat.failed_items}")
    print(f"  In progress: {stage_stat.in_progress_items}")
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

### Streaming Results

For memory-intensive workloads or when you want to process results as they arrive (out-of-order), use `pipeline.stream()`. This returns an async generator yielding results in completion order.

```python
async for result in pipeline.stream(range(100)):
    print(f"Processing result for item {result.id}: {result.value}")
    # Process result immediately, freeing memory
```

Unlike `run()`, which returns a complete list, `stream()` is more memory-efficient for very large datasets.

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

## Priority Queues

AntFlow uses **Priority Queues** internally. You can assign a priority level to items when feeding them into the pipeline.
Lower numbers indicate higher priority (processed first). The default priority is `100`.

- Items with the same priority are processed in FIFO order.
- Priority is preserved across stages (unless a custom `feed` injects with different priority).
- Retries (per-task or per-stage) currently preserve the original priority.

```python
# Expedited items (Priority 10)
await pipeline.feed(vip_items, priority=10)

# Normal items (Priority 100)
await pipeline.feed(regular_items)

# Background/Low priority (Priority 500)
await pipeline.feed(maintenance_items, priority=500)
```

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

## Advanced Internals

> [!WARNING]
> This section covers internal implementation details. These APIs are protected (`_prefix`) and may change between minor versions. Use them with caution when building custom subclasses.

### Internal Queue Structure (`_queues`)

AntFlow manages data flow between stages using a list of internal queues, accessible via `self._queues`.

*   **Type**: `List[asyncio.PriorityQueue]`
*   **Indexing**: `_queues[i]` corresponds to `stages[i]`.
*   **Item Structure**: Items are stored as tuples to ensure correct priority ordering and FIFO stability:
    ```python
    (priority, sequence_id, (payload, attempt))
    ```
    *   **priority** (`int`): Lower number = higher priority.
    *   **sequence_id** (`int`): Monotonically increasing counter to ensure FIFO order for same-priority items.
    *   **payload** (`dict`): The internal item wrapper (see below).
    *   **attempt** (`int`): Current retry attempt number (1-indexed).

### Payload Structure (`_prepare_payload`)

When items enter the pipeline (via `feed` or `run`), they are wrapped in an internal dictionary structure to track metadata and ensure unique identification. The `_prepare_payload(item)` method handles this normalization.

**Internal Payload Format:**
```python
{
    "id": Any,          # Unique identifier (extracted from dict or generated)
    "value": Any,       # The actual data being processed
    "_sequence_id": int # Global sequence ID for result ordering
}
```

*   **ID Extraction**:
    *   If item is a `dict` and has an "id" key, that is used.
    *   Otherwise, the item's index in the input iterable is used as the ID.
*   **Value Extraction**:
    *   If item is a `dict` and has a "value" key, that is used.
    *   Otherwise, the item itself is used as the value.

**Example Override:**
If you need custom ID generation logic, you can override `_prepare_payload` in a subclass:

```python
class CustomPipeline(Pipeline):
    def _prepare_payload(self, item):
        # Custom logic: use 'uuid' field as ID if present
        if isinstance(item, dict) and 'uuid' in item:
            return {
                "id": item['uuid'], 
                "value": item, 
                "_sequence_id": self._msg_counter
            }
        return super()._prepare_payload(item)
```
