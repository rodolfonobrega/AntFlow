# Concurrency Control

AntFlow provides several independent knobs for concurrency. Each solves a different problem — pick only the ones you need.

---

## Quick reference

| I want to… | Use |
|---|---|
| Limit how many items a stage processes in parallel | `workers=N` on the Stage |
| Throttle one specific function in a multi-task stage (short, fast function) | `task_concurrency_limits={"fn": N}` |
| Limit concurrent API calls *inside* a long-running task loop | `call_concurrency=N` + `concurrency_limit()` |
| Limit throughput to N calls per minute (RPM cap) | `call_rate=N` + `rate_limit()` |
| Ensure downstream workers never sit idle waiting in a queue | `pull=True` on the downstream stage |
| Throttle tasks submitted directly via `AsyncExecutor.submit()` | Shared `asyncio.Semaphore` |

---

## `workers` — the baseline

Every stage has a worker pool. This is the simplest form of concurrency control.

```python
Stage(name="fetch", workers=10, tasks=[fetch_data])
# At most 10 items processed concurrently
```

Use this first. Only reach for the other tools when `workers` alone isn't enough.

---

## `pull=True` — demand-driven stages

By default, stages push items forward as soon as they finish. The output sits in the next stage's queue until a worker picks it up.

`pull=True` changes this: a downstream worker must **signal readiness** before it receives the next item. Upstream blocks until a worker is actually waiting — there is **zero buffer** between the stages.

```
Without pull=True:
  [upload] → queue → [queue] → [queue] → [submit+poll workers]
   Items pile up in the queue. Workers may grab stale items.

With pull=True on submit+poll:
  [upload] → (blocked) ←→ [ready worker] → [submit+poll]
   Item handed directly to a worker that is ready RIGHT NOW.
```

**When to use it:** upstream stage is fast (uploads files in seconds), downstream stage is slow and long-running (monitors for minutes). Without `pull=True`, all uploads finish first and queue up, then polling workers scramble for items. With `pull=True`, each item moves downstream only when a poll worker is free — no job waits idle in a queue.

```python
pipeline = Pipeline(stages=[
    Stage("upload", workers=2, tasks=[upload_file]),
    Stage(
        "poll",
        workers=50,
        tasks=[submit_batch, poll_until_done],
        pull=True,   # worker signals "I'm ready" → upload delivers directly
    ),
])
```

**Constraints:** cannot be the first stage; incompatible with `retry="per_stage"`.

---

## `task_concurrency_limits` — gate one function in a multi-task stage

**The problem it solves:** you have a stage with two tasks. One task is long-running (needs many workers). The other task is fast but rate-limited by an external API (needs few concurrent). You cannot satisfy both constraints with a single `workers=N`.

```
I want 50 jobs monitored simultaneously (poll takes minutes)
But the upload API only allows 2 concurrent calls
If workers=2 → only 2 jobs monitored ever
If workers=50 → all 50 try to upload at once → 429 errors
```

**Solution:** 50 workers, but only 2 can be inside `upload()` at the same time. Workers wait at the upload gate, pass through quickly (2 seconds), then spend the next few minutes in `poll_until_done`. The gate empties; all 50 workers eventually end up polling.

```python
Stage(
    "job",
    workers=50,
    tasks=[upload, poll_until_done],
    task_concurrency_limits={"upload": 2},  # only 2 uploading at once
)
```

**How it works:** AntFlow wraps `upload()` with a semaphore. The semaphore is acquired before `upload()` is called and released when it returns. The slot is held for the **entire duration** of the function.

**The critical constraint — this only works for SHORT tasks:**

```python
# BROKEN — only 5 workers will ever run. The other 495 wait forever.
Stage(
    "poll",
    workers=500,
    tasks=[poll_until_done],
    task_concurrency_limits={"poll_until_done": 5},
)
```

`poll_until_done` loops for minutes. During every `await asyncio.sleep(30)`, the semaphore slot is still occupied. Only 5 workers get a slot — the other 495 are blocked permanently. For long-running tasks with internal loops, use `call_concurrency` instead.

**Rule of thumb:** `task_concurrency_limits` only makes sense when the limited function does one thing and returns quickly (seconds). It's a gate workers pass through, not a guard for a long-running loop.

---

## `call_concurrency` — concurrent call cap inside a task

**The problem it solves:** you have 500 workers, each running a long polling loop. Each loop iteration makes one API call. You want all 500 workers alive simultaneously, but you can only have 5 API calls in flight at any instant.

`task_concurrency_limits` cannot help here — it holds the slot for the entire function. With `call_concurrency`, workers grab a slot only for the API call itself and release it immediately after. Workers sleeping between polls hold nothing.

```python
from antflow.context import concurrency_limit

async def poll_until_done(batch_id: str) -> str:
    while True:
        async with concurrency_limit():         # acquires 1 of 5 slots
            status = await api.check(batch_id)  # actual API call
        # slot released — other workers can call now
        if status == "done":
            return batch_id
        await asyncio.sleep(30)                 # sleeping holds NOTHING

Stage(
    "poll",
    workers=500,
    tasks=[poll_until_done],
    pull=True,
    call_concurrency=5,  # max 5 simultaneous API calls across all 500 workers
)
```

**Visual:**
```
Worker 1:  [call✓][sleep 30s......][call✓][sleep 30s......][call✓ DONE]
Worker 2:  [call✓][sleep 30s......][call✓ DONE]
Worker 3:  [WAIT][call✓][sleep 30s......][call✓][sleep...]
...
Worker 500:[WAIT][call✓][sleep 30s......]...

✓ = slot held only for the API call (milliseconds), then released
```

All 500 workers are alive. Only 5 make API calls at any instant. Workers sleeping are not blocking anyone.

---

## `call_rate` — throughput cap (calls per minute)

**The difference from `call_concurrency`:** concurrency limits how many calls are *in flight simultaneously*. Rate limits how many calls happen *per time period* — even if each call is fast, you might only be allowed 100 per minute.

`call_rate` uses a leaky bucket (via `aiolimiter`): the first N calls go through immediately (burst), subsequent calls are spaced evenly.

```python
from antflow.context import rate_limit

async def call_api(item):
    async with rate_limit():           # throttled to 100 calls/min
        return await api.process(item)

Stage(
    "api",
    workers=20,
    tasks=[call_api],
    call_rate=100,          # max 100 acquisitions per period
    call_rate_period=60.0,  # period = 60 seconds (default)
)
```

**Using both together** (concurrency cap + throughput cap):

```python
from antflow.context import concurrency_limit, rate_limit

async def call_api(item):
    async with concurrency_limit():    # at most 5 in flight
        async with rate_limit():       # at most 100 per minute
            return await api.process(item)

Stage(
    "api",
    workers=20,
    tasks=[call_api],
    call_concurrency=5,
    call_rate=100,
    call_rate_period=60.0,
)
```

**Non-blocking capacity check:**

```python
from antflow import call_rate_has_capacity
from antflow.context import rate_limit

async def adaptive_task(item):
    if call_rate_has_capacity():
        async with rate_limit():
            return await api.fast_path(item)
    else:
        return await api.slow_path(item)  # budget exhausted, use fallback
```

---

## Manual semaphores — `AsyncExecutor.submit()`

For custom workflows that bypass `Pipeline`, you can pass a shared semaphore directly to `submit()`:

```python
import asyncio
from antflow import AsyncExecutor

db_semaphore = asyncio.Semaphore(10)

async with AsyncExecutor(max_workers=100) as executor:
    for item in items:
        executor.submit(db_task, item, semaphore=db_semaphore)
    executor.submit(cpu_task, item)  # not limited by db_semaphore
```

---

## `task_concurrency_limits` vs `call_concurrency` — side by side

Both throttle API calls, but they work at different levels:

| | `task_concurrency_limits` | `call_concurrency` |
|---|---|---|
| **Limits** | How many workers can **enter** the function | How many workers can be inside `concurrency_limit()` at once |
| **Slot held for** | Entire function duration (entry → return) | Only the `async with concurrency_limit():` block |
| **Worker while waiting** | Fully blocked, does nothing | Continues running (sleeping, logging, etc.) |
| **Works with loops?** | No — slot held through sleep, breaks everything | Yes — slot released between iterations |
| **Typical task** | Short: one API call, returns immediately | Long: internal loop with periodic calls |
| **Multiple tasks needed?** | Yes — you need a reason to have more workers than the limit | No |

**Decision:**

```
Does your task have an internal loop (polls, retries, streams)?
├── YES → call_concurrency + concurrency_limit()
│         (also add call_rate if you have an RPM limit)
└── NO → Does your stage have multiple tasks?
    ├── YES, and the limited one is short → task_concurrency_limits
    └── NO → just set workers=N
```

---

## Complete example

Upload files to OpenAI, then submit batch jobs and poll until done:

```python
import asyncio
from antflow import Pipeline, Stage
from antflow.context import concurrency_limit

async def upload_file(file_path: str) -> str:
    # ... upload to OpenAI, returns file_id ...
    return file_id

async def submit_batch(file_id: str) -> str:
    response = await openai_client.batches.create(input_file_id=file_id)
    return response.id

async def poll_until_done(batch_id: str) -> str:
    while True:
        async with concurrency_limit():   # only 5 poll calls at once
            batch = await openai_client.batches.retrieve(batch_id)
        if batch.status == "completed":
            return batch_id
        if batch.status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"Batch {batch_id} {batch.status}")
        await asyncio.sleep(30)           # no slot held while sleeping

pipeline = Pipeline(stages=[
    Stage(
        name="upload",
        workers=2,
        tasks=[upload_file],
        queue_capacity=10,  # up to 10 file_paths queued for upload workers
    ),
    Stage(
        name="submit_and_poll",
        workers=500,
        tasks=[submit_batch, poll_until_done],
        pull=True,           # worker signals readiness → upload delivers directly
        call_concurrency=5,  # max 5 concurrent poll API calls
    ),
])

results = await pipeline.run(file_paths)
```

What each parameter does here:
- `workers=500` — 500 jobs monitored simultaneously
- `pull=True` — each file_id handed to a ready poll worker immediately; no queue buildup
- `call_concurrency=5` — only 5 `openai_client.batches.retrieve()` calls in flight at once
- `queue_capacity=10` — up to 10 file_paths wait for upload workers (not uploaded yet)
