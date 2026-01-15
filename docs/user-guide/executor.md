# AsyncExecutor Guide

`AsyncExecutor` provides a `concurrent.futures`-compatible API for executing async tasks concurrently with a worker pool.

## Basic Usage

### Creating an Executor

```python
from antflow import AsyncExecutor

# Create executor with 5 workers
executor = AsyncExecutor(max_workers=5)

# Or use as context manager (recommended)
async with AsyncExecutor(max_workers=5) as executor:
    # Use executor here
    pass
```

### Submitting Tasks

The `submit()` method schedules a single async task for execution:

```python
import asyncio
from antflow import AsyncExecutor

async def process_data(x):
    await asyncio.sleep(0.1)
    return x * 2

async with AsyncExecutor(max_workers=3) as executor:
    # Submit a task
    future = executor.submit(process_data, 42)

    # Wait for result
    result = await future.result()
    print(result)  # 84
```

### Mapping Over Iterables

The `map()` method applies an async function to multiple inputs and returns a list:

```python
import asyncio
from antflow import AsyncExecutor

async def square(x):
    await asyncio.sleep(0.1)
    return x * x

async with AsyncExecutor(max_workers=5) as executor:
    # Map over inputs - returns list directly
    results = await executor.map(square, range(10))
    print(results)  # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

### Streaming Results with map_iter()

For streaming behavior (processing results as they arrive), use `map_iter()`:

```python
import asyncio
from antflow import AsyncExecutor

async def square(x):
    await asyncio.sleep(0.1)
    return x * x

async with AsyncExecutor(max_workers=5) as executor:
    # Stream results with async for
    async for result in executor.map_iter(square, range(10)):
        print(result)  # Prints each result as it arrives
```

**When to use each:**

- **`map()`**: Use for most cases - returns a list directly (like `list(executor.map(...))` in concurrent.futures)
- **`map_iter()`**: Use for streaming, memory-constrained scenarios, or early exit patterns

### Multiple Iterables

`map()` supports multiple iterables, similar to the built-in `map()`:

```python
import asyncio
from antflow import AsyncExecutor

async def add(x, y):
    return x + y

async with AsyncExecutor(max_workers=3) as executor:
    results = await executor.map(add, [1, 2, 3], [4, 5, 6])
    print(results)  # [5, 7, 9]
```

### Processing as Completed

The `as_completed()` method yields futures as they complete:

```python
import asyncio
import random
from antflow import AsyncExecutor

async def fetch_url(url):
    await asyncio.sleep(random.uniform(0.1, 0.5))
    return f"Content from {url}"

async with AsyncExecutor(max_workers=5) as executor:
    urls = [f"http://example.com/page{i}" for i in range(10)]
    futures = [executor.submit(fetch_url, url) for url in urls]

    async for future in executor.as_completed(futures):
        result = await future.result()
        print(f"Got: {result}")

## Wait Strategies

For more complex coordination of multiple futures, use `AsyncExecutor.wait()`. This allows you to wait for a collection of futures with different completion requirements.

```python
from antflow import AsyncExecutor, WaitStrategy

async with AsyncExecutor(max_workers=5) as executor:
    futures = [executor.submit(long_task, i) for i in range(10)]

    # Wait until ALL tasks are completed (default)
    done, pending = await executor.wait(futures, return_when=WaitStrategy.ALL_COMPLETED)

    # Return as soon as ANY task is completed
    done, pending = await executor.wait(futures, return_when=WaitStrategy.FIRST_COMPLETED)

    # Return when ANY task raises an exception
    done, pending = await executor.wait(futures, return_when=WaitStrategy.FIRST_EXCEPTION)
```

| Strategy | Description |
|----------|-------------|
| `ALL_COMPLETED` | Return only when all futures have finished. |
| `FIRST_COMPLETED` | Return when at least one future has finished. |
| `FIRST_EXCEPTION` | Return when any future finishes with an exception. |

---

## map() vs as_completed(): When to Use Each

Understanding the difference between `map()` and `as_completed()` is crucial for choosing the right approach.

### Key Difference: Result Order

| Method | Result Order | Blocking Behavior |
|--------|--------------|-------------------|
| `map()` | **Input order** (deterministic) | Waits for items in sequence |
| `as_completed()` | **Completion order** (non-deterministic) | Returns as soon as any completes |

### Visual Example

Consider processing 5 items where item 0 takes 5 seconds and items 1-4 take 1 second each:

```
Input: [A, B, C, D, E]
       A=5s, B=1s, C=1s, D=1s, E=1s

Timeline with map():
├─ t=1s: B,C,D,E ready (waiting for A)
├─ t=5s: A ready → return [A, B, C, D, E]
└─ Total: 5s, all results at once

Timeline with as_completed():
├─ t=1s: yield B (or C,D,E - whoever finishes first)
├─ t=1s: yield C
├─ t=1s: yield D
├─ t=1s: yield E
├─ t=5s: yield A
└─ Total: 5s, but you see 4 results at t=1s!
```

### Code Comparison

```python
import asyncio
from antflow import AsyncExecutor

async def process(x):
    delay = 3.0 if x == 0 else 0.5
    await asyncio.sleep(delay)
    return f"Result-{x}"

async def main():
    async with AsyncExecutor(max_workers=5) as executor:

        # Using map() - results in INPUT order
        print("=== map() ===")
        results = await executor.map(process, range(5))
        for r in results:
            print(r)
        # Output: Result-0, Result-1, Result-2, Result-3, Result-4
        # (all printed at once after 3s)

        # Using as_completed() - results in COMPLETION order
        print("\n=== as_completed() ===")
        futures = [executor.submit(process, i) for i in range(5)]
        async for future in executor.as_completed(futures):
            print(await future.result())
        # Output: Result-1, Result-2, Result-3, Result-4 (at 0.5s)
        #         Result-0 (at 3s)

asyncio.run(main())
```

### When to Use Each

#### Use `map()` when:

- ✅ **Order matters** - Results must match input order
- ✅ **Batch processing** - You need all results before proceeding
- ✅ **Simple code** - One-liner: `results = await executor.map(...)`
- ✅ **Database inserts** - Maintaining referential integrity

```python
# Example: Processing records where order matters
records = await executor.map(fetch_record, record_ids)
await database.bulk_insert(records)  # Order must match IDs
```

#### Use `as_completed()` when:

- ✅ **Progress feedback** - Show results as they arrive
- ✅ **Early termination** - Stop after finding what you need
- ✅ **Resource efficiency** - Free memory as results complete
- ✅ **Slow outliers** - Don't let one slow task block everything

```python
# Example: Search across multiple sources, return first match
futures = [executor.submit(search, source) for source in sources]
async for future in executor.as_completed(futures):
    result = await future.result()
    if result.found:
        print(f"Found: {result}")
        break  # Early exit!
```

### Summary Table

| Scenario | Recommended Method |
|----------|-------------------|
| Need results in input order | `map()` |
| Show progress to user | `as_completed()` |
| Batch insert to database | `map()` |
| Find first successful result | `as_completed()` |
| Simple parallel processing | `map()` |
| Minimize perceived latency | `as_completed()` |
| Memory-constrained streaming | `map_iter()` |

## Automatic Retries

`AsyncExecutor` supports automatic retries for failed tasks using `tenacity`. You can configure retries for both `submit()` and `map()`.

### Retrying Submissions

```python
async with AsyncExecutor(max_workers=3) as executor:
    # Retry up to 3 times (4 attempts total) with exponential backoff
    # retry_delay sets the initial multiplier (e.g., 0.5s, 1s, 2s...)
    future = executor.submit(
        flaky_task,
        arg,
        retries=3,
        retry_delay=0.5
    )
    result = await future.result()
```

### Retrying Map Operations

```python
async with AsyncExecutor(max_workers=5) as executor:
    # Apply retry logic to all mapped tasks
    results = await executor.map(
        flaky_task,
        items,
        retries=3,
        retry_delay=1.0
    )
```

---

> **Tip:** For advanced scenarios where you need to limit specific tasks within a large worker pool (e.g., rate-limiting a specific API call while keeping others fast), see the [Concurrency Control Guide](concurrency.md).

---

## AsyncFuture

The `AsyncFuture` object represents the result of an async task.

### Methods

- **`result(timeout=None)`**: Wait for and return the result
- **`done()`**: Return True if the future is done
- **`exception()`**: Return the exception (if any)

```python
future = executor.submit(some_task, arg)

# Check if done
if future.done():
    result = await future.result()

# Get exception if failed
exc = future.exception()
if exc:
    print(f"Task failed: {exc}")
```

## Error Handling

Exceptions raised in tasks are captured and re-raised when accessing the result:

```python
import asyncio
from antflow import AsyncExecutor

async def failing_task(x):
    if x < 0:
        raise ValueError("Negative value not allowed")
    return x * 2

async with AsyncExecutor(max_workers=2) as executor:
    future = executor.submit(failing_task, -5)

    try:
        result = await future.result()
    except ValueError as e:
        print(f"Task failed: {e}")
```

## Shutdown

### Manual Shutdown

```python
from antflow import AsyncExecutor

executor = AsyncExecutor(max_workers=3)

# Submit tasks...
future = executor.submit(some_task, arg)
await future.result()

# Shutdown
await executor.shutdown(wait=True)
```

### Shutdown Options

- **`wait=True`** (default): Wait for all pending tasks to complete
- **`cancel_futures=True`**: Cancel all pending futures immediately

```python
# Wait for completion
await executor.shutdown(wait=True)

# Cancel immediately
await executor.shutdown(wait=False, cancel_futures=True)
```

### Context Manager (Recommended)

Using a context manager ensures proper cleanup:

```python
import asyncio
from antflow import AsyncExecutor

async with AsyncExecutor(max_workers=5) as executor:
    # Tasks are automatically waited for on exit
    results = await executor.map(task, items)
# Executor is automatically shut down here
```

## Timeouts

Set timeouts on individual operations:

```python
import asyncio
from antflow import AsyncExecutor

async with AsyncExecutor(max_workers=3) as executor:
    future = executor.submit(slow_task, arg)

    try:
        result = await future.result(timeout=5.0)
    except asyncio.TimeoutError:
        print("Task took too long")
```

Map with timeout:

```python
import asyncio
from antflow import AsyncExecutor

async with AsyncExecutor(max_workers=5) as executor:
    try:
        results = await executor.map(task, items, timeout=10.0)
        print(results)
    except asyncio.TimeoutError:
        print("One of the tasks timed out")
```

## Performance Tips

### Choosing Worker Count

The optimal number of workers depends on your workload:

- **I/O-bound tasks** (API calls, database queries, file I/O): Use more workers (10-100+)
- **Rate-limited APIs**: Match the rate limit (e.g., 10 requests/second = 10 workers)
- **Memory constraints**: Fewer workers if each task uses significant memory
- **Benchmark and adjust**: Start with 10-20 workers and measure performance

```python
from antflow import AsyncExecutor

# For I/O-bound tasks (API calls, database queries)
executor = AsyncExecutor(max_workers=50)

# For rate-limited APIs (e.g., 10 requests/second)
executor = AsyncExecutor(max_workers=10)

# For memory-intensive tasks
executor = AsyncExecutor(max_workers=5)
```

**Note**: Since async workers are coroutines (not threads), CPU core count is not a limiting factor. The main constraints are I/O capacity, rate limits, and memory usage.

### Batching

Process items in batches for better throughput:

```python
import itertools
from antflow import AsyncExecutor

async def process_batch(items):
    return [await process_item(item) for item in items]

def chunks(iterable, size):
    iterator = iter(iterable)
    while batch := list(itertools.islice(iterator, size)):
        yield batch

async with AsyncExecutor(max_workers=5) as executor:
    batches = list(chunks(large_item_list, batch_size=100))
    all_results = await executor.map(process_batch, batches)
    # Flatten results
    results = [item for batch in all_results for item in batch]
```

## Comparison with concurrent.futures

AsyncExecutor is designed to be familiar to users of `concurrent.futures`:

| concurrent.futures | AsyncExecutor |
|-------------------|---------------|
| `ThreadPoolExecutor(max_workers=N)` | `AsyncExecutor(max_workers=N)` |
| `executor.submit(fn, *args)` | `executor.submit(fn, *args)` |
| `list(executor.map(fn, *iterables))` | `await executor.map(fn, *iterables)` |
| `as_completed(futures)` | `executor.as_completed(futures)` |
| `executor.shutdown(wait=True)` | `await executor.shutdown(wait=True)` |
| `future.result()` | `await future.result()` |

Key differences:

- AsyncExecutor works with async functions
- `map()` returns a list directly (no need to wrap in `list()`)
- Uses `async with` instead of `with`
- All operations are awaitable
- `map_iter()` available for streaming behavior

## Complete Example

```python
import asyncio
import aiohttp
from antflow import AsyncExecutor

async def fetch_and_process(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            text = await response.text()
            return len(text)

async def main():
    urls = [
        "http://example.com",
        "http://python.org",
        "http://github.com",
        # ... more URLs
    ]

    async with AsyncExecutor(max_workers=10) as executor:
        print("Fetching URLs...")

        # Simple parallel processing with map()
        results = await executor.map(fetch_and_process, urls)
        for url, length in zip(urls, results):
            print(f"{url}: {length} chars")

asyncio.run(main())
```
