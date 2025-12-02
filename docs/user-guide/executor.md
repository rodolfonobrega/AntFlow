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

The `map()` method applies an async function to multiple inputs:

```python
import asyncio
from antflow import AsyncExecutor

async def square(x):
    await asyncio.sleep(0.1)
    return x * x

async with AsyncExecutor(max_workers=5) as executor:
    # Map over inputs (results are returned in order)
    results = []
    async for result in executor.map(square, range(10)):
        results.append(result)
    print(results)  # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

### Multiple Iterables

`map()` supports multiple iterables, similar to the built-in `map()`:

```python
import asyncio
from antflow import AsyncExecutor

async def add(x, y):
    return x + y

async with AsyncExecutor(max_workers=3) as executor:
    results = []
    async for result in executor.map(add, [1, 2, 3], [4, 5, 6]):
        results.append(result)
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
```

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
    async for result in executor.map(
        flaky_task, 
        items, 
        retries=3, 
        retry_delay=1.0
    ):
        print(result)
```

    result = await future.result()
```

## Concurrency Limits

You can limit the number of concurrent executions for specific tasks, which is useful for rate limiting.

For a detailed overview of all concurrency options, see the [Concurrency Control Guide](concurrency.md).

### In `map()`

Use `max_concurrency` to limit concurrent tasks within a map operation:

```python
async with AsyncExecutor(max_workers=100) as executor:
    # Only 10 tasks will run at once
    async for result in executor.map(api_call, items, max_concurrency=10):
        print(result)
```

### In `submit()`

Use `semaphore` to share a concurrency limit across multiple submit calls:

```python
import asyncio

# Create a semaphore for rate limiting
api_limit = asyncio.Semaphore(10)

async with AsyncExecutor(max_workers=100) as executor:
    futures = []
    for item in items:
        # Share the semaphore across tasks
        f = executor.submit(api_call, item, semaphore=api_limit)
        futures.append(f)
    
    # Wait for results
    results = [await f.result() for f in futures]
```

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
    results = []
    async for result in executor.map(task, items):
        results.append(result)
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
        async for result in executor.map(task, items, timeout=10.0):
            print(result)
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
    batches = chunks(large_item_list, batch_size=100)
    async for results in executor.map(process_batch, batches):
        for result in results:
            print(result)
```

## Comparison with concurrent.futures

AsyncExecutor is designed to be familiar to users of `concurrent.futures`:

| concurrent.futures | AsyncExecutor |
|-------------------|---------------|
| `ThreadPoolExecutor(max_workers=N)` | `AsyncExecutor(max_workers=N)` |
| `executor.submit(fn, *args)` | `executor.submit(fn, *args)` |
| `executor.map(fn, *iterables)` | `executor.map(fn, *iterables)` |
| `as_completed(futures)` | `executor.as_completed(futures)` |
| `executor.shutdown(wait=True)` | `await executor.shutdown(wait=True)` |
| `future.result()` | `await future.result()` |

Key differences:
- AsyncExecutor works with async functions
- Methods return async iterators/futures
- Uses `async with` instead of `with`
- All operations are awaitable

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

        # Process as completed
        futures = [executor.submit(fetch_and_process, url) for url in urls]

        async for future in executor.as_completed(futures):
            try:
                length = await future.result(timeout=30.0)
                print(f"Page length: {length}")
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(main())
```
