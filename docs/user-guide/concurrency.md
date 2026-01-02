# Concurrency Control

AntFlow provides multiple levels of concurrency control to help you manage resources, respect rate limits, and optimize throughput.

## Levels of Control

1.  **Worker Pool**: Limits total concurrent tasks in an executor or stage.
2.  **Task Limits**: Limits specific task functions within a Pipeline Stage.
3.  **Manual Semaphores**: Granular control for individual `.submit()` calls.

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

## 2. Pipeline Task Limits (Granular Rate Limiting)

In a Pipeline, a Stage might have multiple tasks (e.g., `validate` -> `fetch_api` -> `save_db`). You might have 50 workers to keep `validate` and `save_db` fast, but `fetch_api` has a strict rate limit.

**Use Case:** High throughput stage, but one specific function must be rate-limited.

```python
stage = Stage(
    name="Enrichment",
    workers=50,  # High capacity for CPU tasks
    tasks=[validate, fetch_from_api, save_to_db],
    # Only 'fetch_from_api' is limited to 5 concurrent executions
    task_concurrency_limits={
        "fetch_from_api": 5
    }
)
```

*   **Key Benefit:** Workers are not blocked from doing other tasks (`validate`, `save_to_db`) while waiting for the API limit.

---

## 3. Manual Semaphores (Custom Control)

For complex workflows using `.submit()`, you can pass a shared `asyncio.Semaphore` to group tasks under a single limit.

**Use Case:** You are submitting different types of tasks manually and want to limit a specific subset of them.

```python
import asyncio
from antflow import AsyncExecutor

async def main():
    # Create a semaphore for a specific resource (e.g., DB connection)
    db_semaphore = asyncio.Semaphore(10)

    async with AsyncExecutor(max_workers=100) as executor:
        futures = []

        # Submit tasks that need the DB
        for item in items:
            f = executor.submit(
                db_task,
                item,
                semaphore=db_semaphore  # Share the limit
            )
            futures.append(f)

        # Submit other tasks that don't need the DB (unlimited up to max_workers)
        executor.submit(cpu_task, item)
```

---

## Choosing the Right Approach

| Scenario | Recommended Approach |
|----------|---------------------|
| Simple parallel processing | Set `max_workers` appropriately |
| Rate-limited API calls | Create executor with matching workers |
| Mixed task types in Pipeline | Use `task_concurrency_limits` |
| Complex submit workflows | Use shared semaphores |
