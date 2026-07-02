# AntFlow Skill

AntFlow is an async Python library for concurrent task execution and multi-stage pipelines. Use it when the user needs to process items concurrently, build ETL pipelines, or add retry/monitoring to async workflows.

## Install

```bash
pip install antflow
```

AntFlow automatically activates the fastest available event loop on import — **uvloop** on Linux/macOS, **winloop** on Windows. No configuration needed.

## Mental Model

AntFlow has two independent tools:

| Tool | Use When |
|------|----------|
| `AsyncExecutor` | Simple parallel execution — like `concurrent.futures` but async |
| `Pipeline + Stage` | Multi-stage workflows where output of step N feeds step N+1 |

**Tasks are plain async functions** — no decorators, no special base classes.

---

## AsyncExecutor — Parallel Execution

### Simplest usage

```python
import asyncio
from antflow import AsyncExecutor

async def process(item: int) -> int:
    await asyncio.sleep(0.1)
    return item * 2

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        results = await executor.map(process, range(10))
        # [0, 2, 4, 6, 8, 10, 12, 14, 16, 18] — preserves input order

asyncio.run(main())
```

### Submit individual tasks

```python
async with AsyncExecutor(max_workers=5) as executor:
    future = executor.submit(process, 42)
    result = await future.result()  # 84
```

### Stream results in completion order (not input order)

```python
async with AsyncExecutor(max_workers=5) as executor:
    futures = [executor.submit(process, i) for i in range(10)]
    async for future in executor.as_completed(futures):
        result = await future.result()
        print(result)  # arrives as tasks finish
```

### With retries

```python
async with AsyncExecutor(max_workers=5) as executor:
    results = await executor.map(
        flaky_api_call, items,
        retries=3,
        retry_delay=0.5  # exponential backoff
    )
```

### With concurrency limit (semaphore)

```python
semaphore = asyncio.Semaphore(2)  # max 2 simultaneous even with 10 workers

async with AsyncExecutor(max_workers=10) as executor:
    futures = [executor.submit(api_call, i, semaphore=semaphore) for i in range(20)]
    results = [await f.result() for f in futures]
```

### Wait strategies

```python
from antflow import WaitStrategy

done, pending = await executor.wait(futures, return_when=WaitStrategy.FIRST_COMPLETED)
done, pending = await executor.wait(futures, return_when=WaitStrategy.FIRST_EXCEPTION)
done, pending = await executor.wait(futures, return_when=WaitStrategy.ALL_COMPLETED)
```

---

## Pipeline — Multi-Stage Workflows

Data flows: `Stage1 → Stage2 → Stage3`. Each stage has its own worker pool.

### Three equivalent ways to build a pipeline

**Option 1: Stage objects (most control)**
```python
from antflow import Pipeline, Stage

pipeline = Pipeline(stages=[
    Stage("Fetch",   workers=10, tasks=[fetch_data]),
    Stage("Process", workers=5,  tasks=[validate, enrich]),
    Stage("Save",    workers=3,  tasks=[save_to_db]),
])
results = await pipeline.run(range(100), progress=True)
```

**Option 2: Fluent builder (concise)**
```python
results = await (
    Pipeline.create()
    .add("Fetch",   fetch_data,            workers=10, retries=3, retry_policy="per_task")
    .add("Process", validate, enrich,      workers=5)
    .add("Save",    save_to_db,            workers=3)
    .with_tracker(tracker)   # optional StatusTracker
    .collect_results(True)   # default True
    .run(range(100), progress=True)
)
```

**Option 3: One-liner for simple cases**
```python
results = await Pipeline.quick(items, process_task, workers=10, progress=True)

# Multiple tasks in one stage:
results = await Pipeline.quick(items, [fetch, process, save], workers=5)
```

### Working with results

```python
results = await pipeline.run(items)

for r in results:
    if r.is_success:
        print(r.value)    # final output value
    else:
        print(r.error)    # exception

    print(r.id)           # original item identity
```

### Stage configuration reference

```python
Stage(
    name="MyStage",
    workers=5,                              # concurrent workers
    tasks=[task1, task2],                   # run sequentially per item
    retry="per_task",                       # "per_task" | "per_stage"
    task_attempts=3,                        # total attempts (1 + retries)
    task_wait_seconds=1.0,                  # delay between task retries
    stage_attempts=3,                       # (per_stage only) full stage retries
    unpack_args=False,                      # unpack dict items as **kwargs
    task_concurrency_limits={"fn_name": 2}, # cap specific task concurrency (wraps ENTIRE function)
    call_concurrency=5,                     # cap concurrent concurrency_limit() blocks WITHIN tasks
    on_success=async_fn,                    # callback(item_id, result, metadata)
    on_failure=async_fn,                    # callback(item_id, error, metadata)
    on_skip=async_fn,                       # callback(item_id, value, metadata) — fired when skip_if matches
    skip_if=lambda item: condition,         # skip item without processing
    queue_capacity=100,                     # backpressure buffer size
    pull=False,                             # demand-driven mode (see Pull Stages below)
)
```

> **Constraint:** `pull=True` is incompatible with `retry="per_stage"`. First stage cannot be a pull stage.

### Concurrency control: task_concurrency_limits vs call_concurrency

**CRITICAL DISTINCTION — get this wrong and your pipeline breaks:**

**`task_concurrency_limits`** — wraps the ENTIRE function. The semaphore is held from function entry to function return. Use only for **short, single-call tasks** in a **multi-task stage**.

```python
# CORRECT: upload is a fast gate, poll_loop is long (workers accumulate there)
# WHY 50 workers? Because poll_loop runs for minutes — I want 50 jobs monitored.
# WHY limit upload? API only allows 2 concurrent uploads.
Stage("job", workers=50, tasks=[upload, poll_loop],
      task_concurrency_limits={"upload": 2}, call_concurrency=5)

# CORRECT: validate+save benefit from 50 workers; fetch_api has external rate limit
Stage("Enrich", workers=50, tasks=[validate, fetch_api, save],
      task_concurrency_limits={"fetch_api": 5})

# BROKEN: single long-running task — just blocks all workers permanently
Stage("Poll", workers=500, tasks=[poll_until_done],
      task_concurrency_limits={"poll_until_done": 5})
# → Only 5 workers ever run! Use call_concurrency instead.

# POINTLESS: all tasks are short — just use workers=2
Stage("job", workers=50, tasks=[upload, check],
      task_concurrency_limits={"upload": 2})
# → If no task needs the extra workers, reduce workers directly.
```

**Ask yourself:** why do I need more workers than the limit? If no other task in the
stage benefits from the extra workers, just set `workers=N` and skip the limit entirely.

**`call_concurrency`** — limits only the code inside `async with concurrency_limit():`. All workers stay alive; the slot is released immediately after the block. Use for **long-running tasks with internal loops** that make periodic API calls.

```python
from antflow.context import concurrency_limit

async def poll_until_done(batch_id: str):
    while True:
        async with concurrency_limit():    # acquire slot briefly
            status = await api.check(batch_id)
        # slot released here — other workers can poll now
        if status == "done":
            return batch_id
        await asyncio.sleep(30)            # NOT holding any slot

# CORRECT: 500 jobs monitored, only 5 API calls at once
Stage("Poll", workers=500, tasks=[poll_until_done],
      pull=True, call_concurrency=5)
```

**When to use what:**
- `task_concurrency_limits`: multi-task stage where one short task has an external rate limit, but another task needs many workers (e.g., upload gate + long poll)
- `call_concurrency` + `concurrency_limit()`: task has an internal loop and you want to limit API calls without blocking the whole worker
- Combine both: fast gate limited by `task_concurrency_limits` + loop limited by `call_concurrency`
- Single task, simple limit: just set `workers=N` — don't overcomplicate it

---

## Retry Strategies

### per_task (default) — each item retries independently
```python
Stage("Download", workers=10, tasks=[download],
      retry="per_task", task_attempts=5, task_wait_seconds=0.5)
```

### per_stage — entire stage re-runs if anything fails (transactional)
```python
Stage("DB Write", workers=3, tasks=[save],
      retry="per_stage", stage_attempts=3)
```

---

## Monitoring

### Progress bar only
```python
results = await pipeline.run(items, progress=True)
```

### Built-in dashboards
```python
results = await pipeline.run(items, dashboard="compact")    # summary
results = await pipeline.run(items, dashboard="detailed")   # per-stage table
results = await pipeline.run(items, dashboard="full")       # workers + errors
```

### Event-driven tracking
```python
from antflow import StatusTracker

tracker = StatusTracker(
    on_status_change=lambda e: print(f"{e.item_id}: {e.status}"),
    on_task_start=lambda e: print(f"Starting {e.task_name}"),
    on_task_complete=lambda e: print(f"Done in {e.duration:.2f}s"),
    on_task_retry=lambda e: print(f"Retrying: {e.error}"),
    on_task_fail=lambda e: print(f"Failed: {e.error}"),
)

pipeline = Pipeline(stages=[...], status_tracker=tracker)
results = await pipeline.run(items)

stats  = tracker.get_stats()          # {"completed": N, "failed": M, ...}
history = tracker.get_history(0)     # full StatusEvent log for item id=0
failed  = tracker.get_failed_items() # List[FailedItem] with error, stage, attempts
summary = tracker.get_error_summary()# ErrorSummary: total, by_type, by_stage
```

### Report task progress from inside a task
```python
from antflow import set_task_status

async def poll_job(job_id: str):
    for i in range(60):
        status = await check_status(job_id)
        set_task_status(f"Polling attempt {i}, status={status}")
        if status == "done":
            return await fetch_result(job_id)
        await asyncio.sleep(1)
```

---

## Advanced Patterns

### Stream results as they complete
```python
async for result in pipeline.stream(items):
    print(result.value)  # arrives in completion order, not input order

# With backpressure — pipeline blocks until consumer drains a slot
async for result in pipeline.stream(items, buffer_size=10):
    await slow_consumer(result)
```

### Feed items from a sequence or async generator

```python
# feed() — from any sequence
await pipeline.start()
await pipeline.feed(["item1"])                             # starts at stage 0
await pipeline.feed(["item2"], target_stage="SaveStage")  # skip to Save
await pipeline.join()

# feed_async() — from an async iterable (e.g. async generator, async DB cursor)
async def read_from_db():
    async for row in db.cursor.execute("SELECT id FROM jobs"):
        yield row["id"]

await pipeline.start()
await pipeline.feed_async(read_from_db())
await pipeline.feed_async(read_from_db(), target_stage="ProcessStage", priority=0)
await pipeline.join()
```

### Priority queue — urgent items jump the queue
```python
await pipeline.start()
await pipeline.feed(["urgent"],    priority=0)    # processed first
await pipeline.feed(["normal"],    priority=100)
await pipeline.feed(["background"],priority=500)
await pipeline.join()
```

### Skip items conditionally
```python
stage = Stage("Transform", workers=5, tasks=[transform],
              skip_if=lambda item: item.get("already_done"),
              on_skip=lambda item_id, val, meta: log_skip(item_id))
# Skipped items pass through unchanged; on_success is NOT called for skipped items
```

### Pull Stages — demand-driven / just-in-time processing

By default, each stage pushes items into the next stage's queue as fast as it can. With `pull=True`, a stage only receives an item when one of its workers is actually ready — the upstream is blocked until demand arrives. There is no buffer between the two stages; items are handed off directly to a ready worker.

```python
pipeline = Pipeline(stages=[
    Stage("Fetch",   workers=10, tasks=[fetch_url]),
    Stage("Embed",   workers=4,  tasks=[call_embedding_api], pull=True),
    #                                                         ^^^^^^^^^
    # The 4 embed workers control the pace — upstream only produces
    # when an embed worker is free. Never more than 4 items in-flight
    # between stages, regardless of how fast Fetch runs.
])
results = await pipeline.run(urls)
```

**When to use `pull=True`:**
- Downstream is expensive/rate-limited and you don't want upstream to buffer aggressively
- You want `workers` to be the hard cap on concurrency between two stages
- Replacing manual `queue_capacity` tuning with automatic pacing

**OpenAI Batch API example — upload prefetch + exact poll control:**

A common pattern: upload workers keep a buffer of pre-uploaded files ready, but poll workers only receive a file when they are free to submit and monitor it immediately — no unobserved jobs.

```python
pipeline = Pipeline(stages=[
    Stage(
        name="Upload",
        workers=2,
        tasks=[upload_file],
        queue_capacity=10,   # pre-upload up to 10 files ahead
    ),
    Stage(
        name="Submit_and_Poll",
        workers=50,
        tasks=[submit_batch, poll_until_done],
        pull=True,           # only receives a file when a worker is free to watch it
    ),
])
```

- Upload workers run ahead and fill the buffer — they are never idle waiting for a poll slot.
- When a poll worker finishes, it pulls the next pre-uploaded file directly and submits immediately.
- At most `50` jobs are ever in-flight on OpenAI; none sit unmonitored in a queue.

See `examples/pull_stage_openai_batch.py` for a full runnable version.


### Pipeline as context manager

```python
async with Pipeline(stages=[...]) as pipeline:
    await pipeline.feed(items)
    await pipeline.join()
    results = pipeline.results  # property — same as return value of run()
```

### Shutdown pipeline explicitly

```python
await pipeline.shutdown()  # hard stop — cancels in-flight work
```

### Inspect pipeline state

```python
stats    = pipeline.get_stats()              # PipelineStats
workers  = pipeline.get_worker_states()      # Dict[name, WorkerState]
metrics  = pipeline.get_worker_metrics()     # Dict[name, WorkerMetrics]
snapshot = pipeline.get_dashboard_snapshot() # DashboardSnapshot
errors   = pipeline.get_error_summary()      # ErrorSummary
```

### Stage callbacks
```python
async def on_success(item_id, result, metadata):
    await update_dashboard(item_id, "ok")

async def on_failure(item_id, error, metadata):
    await notify_slack(f"Item {item_id} failed: {error}")

stage = Stage("Process", workers=5, tasks=[process],
              on_success=on_success, on_failure=on_failure)
```

---

## Common Recipes

### Rate-limited API (N calls/second)
```python
# Using semaphore in executor
sem = asyncio.Semaphore(5)  # max 5 concurrent
async with AsyncExecutor(max_workers=20) as executor:
    results = await executor.map(lambda item: api_call(item, sem), items)

# Or using task_concurrency_limits in pipeline (SHORT tasks only)
Stage("API", workers=20, tasks=[api_call],
      task_concurrency_limits={"api_call": 5})
```

### ETL pipeline with error handling
```python
async def extract(url: str) -> dict:
    async with aiohttp.ClientSession() as s:
        r = await s.get(url)
        return await r.json()

async def transform(data: dict) -> dict:
    return {k: v.strip() for k, v in data.items()}

async def load(data: dict) -> str:
    await db.insert(data)
    return data["id"]

results = await (
    Pipeline.create()
    .add("Extract",   extract,   workers=10, retries=3)
    .add("Transform", transform, workers=5)
    .add("Load",      load,      workers=3,  retries=2)
    .run(urls, progress=True)
)

failed = [r for r in results if not r.is_success]
```

### N jobs processando, mas só K API calls ao mesmo tempo

Use `call_concurrency` + `concurrency_limit()` when you want many workers alive (each monitoring their job) but only a few API calls happening simultaneously:

```python
from antflow import Pipeline, Stage
from antflow.context import concurrency_limit

async def poll_openai_batch(batch_id: str) -> list:
    client = AsyncOpenAI()
    while True:
        async with concurrency_limit():  # ← only 5 concurrent API calls
            batch = await client.batches.retrieve(batch_id)
        set_task_status(f"status={batch.status}")
        if batch.status == "completed":
            return await download_results(batch.output_file_id)
        if batch.status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"Batch {batch_id} {batch.status}")
        await asyncio.sleep(10)  # sleeping does NOT hold a rate-limit slot

pipeline = Pipeline(stages=[
    Stage("upload", workers=2, tasks=[upload_file], queue_capacity=10),
    Stage(
        "poll",
        workers=500,             # 500 jobs monitored simultaneously
        tasks=[poll_openai_batch],
        pull=True,               # only start when a worker is free
        call_concurrency=5,      # max 5 API calls at once
    ),
])
results = await pipeline.run(file_paths)
```

**Simple alternative** (fewer jobs but simpler): just set workers=N to directly cap parallelism:

```python
# If you only need 20 jobs in-flight total:
results = await Pipeline.quick(
    batch_ids,
    poll_openai_batch,
    workers=20,          # each worker handles 1 job at a time
)
# The other 980 items wait in the queue for a worker to free up
```

---

## Exceptions

```python
from antflow.exceptions import (
    AntFlowError,           # base
    ExecutorShutdownError,  # used executor after shutdown
    PipelineError,          # pipeline runtime error
    StageValidationError,   # bad stage config
)
```

---

## Public API Exports

```python
from antflow import (
    # Core
    AsyncExecutor,      # concurrent.futures-style async executor
    AsyncFuture,        # future returned by executor.submit()
    Pipeline,           # multi-stage pipeline
    PipelineBuilder,    # returned by Pipeline.create()
    Stage,              # single pipeline stage config
    StatusTracker,      # event-driven monitoring
    WaitStrategy,       # FIRST_COMPLETED | FIRST_EXCEPTION | ALL_COMPLETED
    set_task_status,    # update dashboard label from inside a task
    concurrency_limit,  # async context manager for call_concurrency throttling
    rate_limit,         # async context manager for call_rate throttling

    # Result / stats dataclasses
    PipelineResult,     # .value, .error, .id, .is_success, .sequence_id, .metadata
    PipelineStats,      # .items_processed, .items_failed, .items_in_flight, .queue_sizes
    StageStats,         # per-stage counts
    WorkerState,        # .worker_name, .stage, .status, .current_item_id, .current_task
    WorkerMetrics,      # .items_processed, .items_failed, .avg_processing_time
    WorkerStatus,       # "idle" | "busy"

    # Monitoring / events
    StatusEvent,        # emitted by StatusTracker on item state change
    StatusType,         # "queued"|"in_progress"|"completed"|"failed"|"retrying"|"skipped"
    TaskEvent,          # emitted per task execution
    TaskEventType,      # "start"|"complete"|"retry"|"fail"
    FailedItem,         # .item_id, .error, .error_type, .stage, .attempts
    ErrorSummary,       # .total_failed, .errors_by_type, .errors_by_stage, .failed_items
    DashboardSnapshot,  # passed to custom dashboards
    DashboardProtocol,  # ABC for custom dashboard implementations

    # Exceptions
    AntFlowError,
    ExecutorShutdownError,
    PipelineError,
    StageValidationError,
    TaskFailedError,

    # Types
    TaskFunc,           # Callable[[Any], Awaitable[Any]]
)
```
