# Concurrency Control

AntFlow provides multiple levels of concurrency control to help you manage resources, respect rate limits, and optimize throughput.

## Levels of Control

1.  **Worker Pool**: Limits total concurrent tasks in an executor or stage.
2.  **Task Concurrency Limits**: Limits specific task functions within a multi-task Pipeline Stage.
3.  **Call Concurrency**: Limits API calls *inside* long-running tasks (via `rate_limit()`).
4.  **Manual Semaphores**: Granular control for individual `.submit()` calls.

---

## 1. Worker Pool (Global Limit)

The most basic control is the number of workers. This sets the hard limit on how many tasks can run in parallel for that executor or stage.

### In AsyncExecutor

```python
from antflow import AsyncExecutor

# Maximum 10 tasks running at once
async with AsyncExecutor(max_workers=10) as executor:
    results = await executor.map(task, items)
```

### In Pipeline Stage

```python
from antflow import Stage

# This stage will never run more than 5 tasks simultaneously
stage = Stage(
    name="Processing",
    workers=5,
    tasks=[my_task]
)
```

---

## 2. Task Concurrency Limits

### Why it exists

You have a stage with **multiple tasks** where one task is long (needs many workers) and another task has an external rate limit (needs few concurrent). You can't satisfy both with a single `workers=N`.

**The problem it solves:**

```
I want 50 jobs being monitored (poll takes minutes)
But uploading is rate-limited to 2 concurrent by the API
If workers=2, I only have 2 jobs monitored
If workers=50, all 50 try to upload at once → 429 errors
```

**The solution:** 50 workers pass through a rate-limited upload gate (2 at a time), then accumulate in the long poll phase. Eventually all 50 are monitoring their jobs.

### How it works

The semaphore wraps the **entire function call** — acquired before entry, released after return. Workers wait at that step until they get a slot, then pass through and move on to the next task.

```
Worker 1:  [upload ✓] → [poll_until_done ← stays here for minutes]
Worker 2:  [upload ✓] → [poll_until_done ← stays here for minutes]
Worker 3:  [WAIT...] → [upload ✓] → [poll_until_done ← stays here]
Worker 4:  [WAIT...] → [upload ✓] → [poll_until_done ← stays here]
...eventually all 50 workers are in poll_until_done
```

### When to use it

`task_concurrency_limits` makes sense **only** when ALL of these are true:

1. Your stage has **multiple tasks** (`tasks=[task_a, task_b]`)
2. One task is the reason you need many workers (it's long-running or benefits from parallelism)
3. Another task has an external rate limit (API cap, DB connection pool)
4. The rate-limited task is **short** (seconds) — it's a gate workers pass through quickly

```python
stage = Stage(
    name="Enrichment",
    workers=50,
    tasks=[validate, fetch_from_api, save_to_db],
    task_concurrency_limits={
        "fetch_from_api": 5
    }
)
```

Here, 50 workers run `validate` and `save_to_db` without limits, but only 5 can call `fetch_from_api` at the same time. Workers waiting for a slot are paused between `validate` and `fetch_from_api` — they aren't doing anything else.

### When NOT to use it

**If you have a single task** — just set `workers=N`. There's no reason to have 50 workers and limit the only task to 5. Use `workers=5` directly.

**If the limited task is long-running (has a loop)** — the semaphore is held the ENTIRE time the function runs. With `task_concurrency_limits={"poll": 5}` on a function that loops for minutes, only 5 workers ever run. The other 495 are permanently blocked. Use `call_concurrency` instead.

### How the limited task interacts with other tasks

Once a worker passes through the rate-limited task, it moves on freely. Workers already in the polling phase do NOT compete with the upload semaphore — the semaphore only applies when a worker is *entering* that specific function.

The semaphore doesn't slow things down — it prevents 429 errors. Without it, all 50 workers would hit the upload API simultaneously. With it, they wait politely. The throughput is the same because the API is the bottleneck regardless.

### How it breaks things

**Example of misuse:**

```python
async def poll_until_done(batch_id: str):
    """This task runs for minutes — it loops internally."""
    while True:
        status = await api.check(batch_id)
        if status == "done":
            return batch_id
        await asyncio.sleep(30)  # sleeping but STILL holding the semaphore!

# BROKEN: Only 5 workers will EVER run. The other 495 are permanently blocked.
Stage(
    "poll",
    workers=500,
    tasks=[poll_until_done],
    task_concurrency_limits={"poll_until_done": 5},
)
```

**What happens:** The semaphore wraps the entire `poll_until_done` call. Even during `await asyncio.sleep(30)`, the slot is occupied. Only 5 polls happen in parallel — you'll never have more than 5 jobs being monitored. The other 495 workers are dead weight.

**Visual timeline (BROKEN):**
```
Worker 1:   [===poll_until_done (5 min)===]   # holds semaphore entire time
Worker 2:   [===poll_until_done (5 min)===]
Worker 3:   [===poll_until_done (5 min)===]
Worker 4:   [===poll_until_done (5 min)===]
Worker 5:   [===poll_until_done (5 min)===]
Worker 6:   [BLOCKED.........................] # waiting for semaphore
Worker 7:   [BLOCKED.........................] # waiting for semaphore
...
Worker 500: [BLOCKED.........................] # waiting for semaphore
```

### Example: why you need many workers + a rate limit on one task

**The reasoning:**

1. I want 50 batch jobs being monitored on OpenAI simultaneously (poll runs for minutes)
2. Before monitoring, each job needs an upload (takes 2 seconds, API allows max 2 concurrent)
3. I can't use `workers=2` — that gives me only 2 jobs monitored
4. I can't use `workers=50` without a limit — all 50 upload at once, API rejects 48

**Solution:** 50 workers + limit upload to 2. Workers pass through the upload gate quickly and accumulate in the poll phase.

```python
async def upload(file_path: str) -> str:
    """Fast gate (2 seconds). The reason for task_concurrency_limits."""
    return await openai.files.create(file=open(file_path, "rb"))

async def poll_until_done(file_id: str) -> dict:
    """Long-running (minutes). The reason for 50 workers."""
    batch = await openai.batches.create(input_file_id=file_id)
    while True:
        async with rate_limit():
            status = await openai.batches.retrieve(batch.id)
        if status.status == "completed":
            return status
        await asyncio.sleep(30)

Stage(
    "job",
    workers=50,
    tasks=[upload, poll_until_done],
    task_concurrency_limits={"upload": 2},  # gate: only 2 uploading at once
    call_concurrency=5,                     # within poll loop: only 5 API calls at once
)
```

**Timeline:**
```
t=0s:    Workers 1,2 upload (2s each). Workers 3-50 wait for upload slot.
t=2s:    Workers 1,2 → poll. Workers 3,4 upload. Workers 5-50 wait.
t=4s:    Workers 3,4 → poll. Workers 5,6 upload. Workers 7-50 wait.
...
t=50s:   All 50 workers are now in poll. All 50 jobs being monitored.
         Upload gate is empty — no more items to process.
```

### When it makes NO sense

```python
# POINTLESS: single task — just use workers=5
Stage("job", workers=50, tasks=[call_api],
      task_concurrency_limits={"call_api": 5})

# POINTLESS: all tasks are short — just use workers=2
Stage("job", workers=50, tasks=[upload, check],
      task_concurrency_limits={"upload": 2})
# Both take 100ms → 50 workers adds nothing. workers=2 is identical.
```

Ask yourself: **why do I need more workers than the limit?** The answer must be "because another task in this stage needs them." If there's no other task that benefits from the extra workers, just reduce `workers`.

---

## 3. Call Concurrency (Rate-Limiting Inside Tasks)

### What it does

`call_concurrency` limits concurrent API calls **within** long-running tasks — without blocking the entire task from running. All workers remain active; only the specific code wrapped by `rate_limit()` is throttled.

### How it works internally

1. You set `call_concurrency=N` on the Stage — AntFlow creates a shared `asyncio.Semaphore(N)`.
2. Inside your task, you wrap each API call with `async with rate_limit():`.
3. The semaphore is acquired only during the `rate_limit()` block, then released immediately.
4. Workers sleeping, logging, or doing other work do NOT hold a slot.

### When to use it

**Use `call_concurrency` when:**
- Your task is **long-running** and has an internal loop (polling, retrying, streaming)
- You want many workers alive simultaneously (each monitoring their own job)
- But the actual API calls must be throttled (e.g., only 5 concurrent requests)
- Workers should release the rate-limit slot between calls (e.g., during `sleep`)

```python
from antflow import Pipeline, Stage
from antflow.context import rate_limit

async def poll_until_done(batch_id: str) -> str:
    while True:
        async with rate_limit():                  # acquires 1 of 5 slots
            status = await api.check(batch_id)    # the actual API call
        # slot released immediately after the API call
        if status == "done":
            return batch_id
        await asyncio.sleep(30)                   # sleeping does NOT hold a slot

pipeline = Pipeline(stages=[
    Stage(
        name="poll",
        workers=500,
        tasks=[poll_until_done],
        pull=True,
        call_concurrency=5,    # only 5 API calls at once, across all 500 workers
    ),
])
```

**Visual timeline (CORRECT):**
```
Worker 1:   [poll✓] [sleep 30s...] [poll✓] [sleep 30s...] [poll✓ DONE!]
Worker 2:   [poll✓] [sleep 30s...] [poll✓ DONE!]
Worker 3:   [WAIT] [poll✓] [sleep 30s...] [poll✓] [sleep 30s...] [poll✓ DONE!]
Worker 4:   [WAIT] [poll✓] [sleep 30s...] [poll✓ DONE!]
Worker 5:   [poll✓] [sleep 30s...] [poll✓] [sleep 30s...] [poll✓ DONE!]
...
Worker 500: [WAIT] [poll✓] [sleep 30s...] ...

(✓ = slot acquired briefly for the API call, then released)
```

All 500 workers are alive and monitoring their jobs. Only 5 are making API calls at any given instant. Workers that are sleeping are NOT holding slots — they yield to others.

### When NOT to use it

- If your task is a single short function (use `task_concurrency_limits` instead — simpler)
- If you don't need fine-grained control within the task body
- If every worker should only do one API call total (just set `workers=N`)

---

## 4. Manual Semaphores (Custom Control)

For complex workflows using `.submit()`, you can pass a shared `asyncio.Semaphore` to group tasks under a single limit.

**Use Case:** You are submitting different types of tasks manually and want to limit a specific subset of them.

```python
import asyncio
from antflow import AsyncExecutor

async def main():
    db_semaphore = asyncio.Semaphore(10)

    async with AsyncExecutor(max_workers=100) as executor:
        futures = []

        for item in items:
            f = executor.submit(
                db_task,
                item,
                semaphore=db_semaphore
            )
            futures.append(f)

        # Other tasks not limited by the DB semaphore
        executor.submit(cpu_task, item)
```

---

## Comparison: task_concurrency_limits vs call_concurrency

| | `task_concurrency_limits` | `call_concurrency` |
|---|---|---|
| **What it limits** | How many workers can **enter** a task function | How many workers can be **inside `rate_limit()`** at once |
| **Granularity** | Entire function call (from start to return) | Specific code block within the function |
| **Worker behavior while limited** | Worker is fully blocked, doing nothing | Worker continues running (sleeping, logging, etc.) |
| **When the slot is held** | Entire duration of the function | Only during `async with rate_limit():` block |
| **Best for** | Multi-task stages with one slow step | Long-running tasks with periodic API calls |
| **Typical task duration** | Milliseconds to seconds | Minutes to hours |
| **Typical task structure** | Single API call, returns immediately | Loop with sleep + periodic checks |
| **How many workers are active** | Only N workers run the limited function; rest wait | All workers run; only N make API calls simultaneously |

### Decision flowchart

```
Is your task a loop that runs for a long time (minutes/hours)?
├── YES → Use call_concurrency + rate_limit()
└── NO → Does your stage have multiple task functions?
    ├── YES → Use task_concurrency_limits on the slow one
    └── NO → Just set workers=N (simplest)
```

---

## Choosing the Right Approach

| Scenario | Recommended Approach |
|----------|---------------------|
| Simple parallel processing | Set `max_workers` / `workers` appropriately |
| Rate-limited API (one call per item, returns fast) | `task_concurrency_limits` or just set workers=N |
| Multi-task stage, throttle one step | `task_concurrency_limits` |
| Long-running task with periodic API calls (polling) | `call_concurrency` + `rate_limit()` |
| 500 jobs monitored, only 5 API calls at once | `call_concurrency=5` + `rate_limit()` around each call |
| Complex submit workflows in AsyncExecutor | Shared `asyncio.Semaphore` |

---

## Complete Example: OpenAI Batch API Pipeline

This example ties everything together — upload prefetch, pull stages, and call concurrency:

```python
import asyncio
from antflow import Pipeline, Stage
from antflow.context import rate_limit

async def upload_file(file_path: str) -> str:
    """Upload a JSONL file to OpenAI. Returns file_id."""
    async with aiohttp.ClientSession() as session:
        # ... upload logic ...
        return file_id

async def submit_batch(file_id: str) -> str:
    """Submit the file as a batch job. Returns batch_id."""
    response = await openai_client.batches.create(input_file_id=file_id)
    return response.id

async def poll_until_done(batch_id: str) -> str:
    """Poll until the batch job completes."""
    while True:
        async with rate_limit():  # <-- only 5 concurrent poll calls
            batch = await openai_client.batches.retrieve(batch_id)
        if batch.status == "completed":
            return batch_id
        if batch.status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"Batch {batch_id} {batch.status}")
        await asyncio.sleep(30)  # no rate-limit slot held during sleep

pipeline = Pipeline(stages=[
    Stage(
        name="upload",
        workers=2,
        tasks=[upload_file],
        queue_capacity=10,       # keep 10 files pre-uploaded and ready
    ),
    Stage(
        name="submit_and_poll",
        workers=500,             # 500 jobs monitored simultaneously
        tasks=[submit_batch, poll_until_done],
        pull=True,               # submit only when a worker is free
        call_concurrency=5,      # max 5 concurrent poll API calls
    ),
])

results = await pipeline.run(file_paths)
```

**What this achieves:**
- 2 upload workers keep 10 files pre-uploaded in a buffer
- Submit only happens when a poll worker is free (`pull=True`)
- 500 jobs are actively being monitored on OpenAI
- Only 5 poll API calls happen at any instant (`call_concurrency=5`)
- Workers sleep between polls without holding rate-limit slots
