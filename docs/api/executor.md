# AsyncExecutor API

The `antflow.executor` module provides a familiar interface for concurrent async execution, modeled after Python's `concurrent.futures`.

## Overview

The **[AsyncExecutor][antflow.executor.AsyncExecutor]** manages a pool of workers to execute async functions concurrently. It is ideal for simple parallel processing tasks where you don't need the full complexity of a multi-stage pipeline.

Key features:
- **`submit()`**: Schedule a single task.
- **`map()`**: Apply a function to an iterable concurrently.
- **`as_completed()`**: Iterate over futures as they finish.
- **`wait()`**: Wait for a collection of futures with flexible conditions.

## Usage Example

```python
import asyncio
from antflow import AsyncExecutor

async def process_item(x):
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    # Use as a context manager
    async with AsyncExecutor(max_workers=5) as executor:
        
        # 1. Submit a single task
        future = executor.submit(process_item, 10)
        result = await future.result()
        print(f"Result: {result}")

        # 2. Map over a list
        async for res in executor.map(process_item, range(5)):
            print(f"Mapped: {res}")
            
asyncio.run(main())
```

## Wait Strategies

When using `executor.wait()`, you can control when the function returns using the `return_when` parameter:

| Strategy | Description |
|----------|-------------|
| `ALL_COMPLETED` | (Default) Returns only when **all** futures have finished. |
| `FIRST_COMPLETED` | Returns as soon as **one** future finishes. Useful for racing tasks. |
| `FIRST_EXCEPTION` | Returns as soon as **one** future raises an exception. Useful for fail-fast scenarios. |

## Class Reference

For complete class definitions, see the [source code](../../antflow/executor.py).
