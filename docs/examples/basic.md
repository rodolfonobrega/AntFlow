# Basic Examples

Simple examples to get started with AntFlow.

## AsyncExecutor Examples

### Using map()

The `map()` method applies an async function to multiple inputs and returns a list:

```python
import asyncio
from antflow import AsyncExecutor

async def square(x: int) -> int:
    """Square a number with a small delay."""
    await asyncio.sleep(0.1)
    return x * x

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        # Map returns list directly
        results = await executor.map(square, range(10))
        print(results)  # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]

asyncio.run(main())
```

**Output:**
```
[0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

### Using submit()

Submit individual tasks and collect results:

```python
import asyncio
from antflow import AsyncExecutor

async def cube(x: int) -> int:
    """Cube a number with a small delay."""
    await asyncio.sleep(0.15)
    return x * x * x

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        # Submit individual tasks
        futures = [executor.submit(cube, i) for i in range(5)]

        # Collect results
        results = [await f.result() for f in futures]
        print(results)  # [0, 1, 8, 27, 64]

asyncio.run(main())
```

**Output:**
```
[0, 1, 8, 27, 64]
```

### Using map_iter() for Streaming

For streaming results as they arrive (useful for large datasets or progress feedback):

```python
import asyncio
from antflow import AsyncExecutor

async def square(x: int) -> int:
    await asyncio.sleep(0.1)
    return x * x

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        # Stream results with async for
        async for result in executor.map_iter(square, range(10)):
            print(f"Got: {result}")

asyncio.run(main())
```

### Using as_completed()

Process results as they complete (not in input order):

```python
import asyncio
from antflow import AsyncExecutor

async def square(x: int) -> int:
    await asyncio.sleep(0.1)
    return x * x

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        futures = [executor.submit(square, i) for i in range(5, 10)]

        async for future in executor.as_completed(futures):
            result = await future.result()
            print(f"Completed: {result}")

asyncio.run(main())
```

**Output:**
```
Completed: 81
Completed: 25
Completed: 49
Completed: 36
Completed: 64
```

> **Note:** The order varies because `as_completed()` returns results as they finish, not in input order.

### map() vs as_completed() Comparison

This example shows the key difference between the two approaches:

```python
import asyncio
from antflow import AsyncExecutor

async def variable_delay_task(x: int) -> str:
    # Item 0 is slow, others are fast
    delay = 2.0 if x == 0 else 0.3
    await asyncio.sleep(delay)
    return f"Result-{x}"

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        items = range(5)

        # map(): Results in INPUT order
        print("=== map() - Input Order ===")
        results = await executor.map(variable_delay_task, items)
        for r in results:
            print(f"  {r}")

        # as_completed(): Results in COMPLETION order
        print("\n=== as_completed() - Completion Order ===")
        futures = [executor.submit(variable_delay_task, i) for i in items]
        async for future in executor.as_completed(futures):
            print(f"  {await future.result()}")

asyncio.run(main())
```

**Output:**
```
=== map() - Input Order ===
  Result-0
  Result-1
  Result-2
  Result-3
  Result-4

=== as_completed() - Completion Order ===
  Result-1
  Result-3
  Result-2
  Result-4
  Result-0
```

**Key Insight:**

- `map()` waits for slow item 0 before returning anything
- `as_completed()` returns fast items (1-4) immediately, then slow item (0)

## Pipeline Examples

### Two-Stage ETL Pipeline

Extract, transform, and load data through a pipeline:

```python
import asyncio
from antflow import Pipeline, Stage

async def extract(x: int) -> str:
    """Extract/fetch data."""
    await asyncio.sleep(0.05)
    return f"data_{x}"

async def transform(x: str) -> str:
    """Transform data."""
    await asyncio.sleep(0.05)
    return x.upper()

async def load(x: str) -> str:
    """Load/save data."""
    await asyncio.sleep(0.05)
    return f"saved_{x}"

async def main():
    # Define stages
    extract_stage = Stage(
        name="Extract",
        workers=3,
        tasks=[extract],
        retry="per_task",
        task_attempts=3
    )

    transform_stage = Stage(
        name="Transform",
        workers=2,
        tasks=[transform, load],  # Multiple tasks in sequence
        retry="per_task",
        task_attempts=3
    )

    # Create pipeline
    pipeline = Pipeline(
        stages=[extract_stage, transform_stage],
        collect_results=True
    )

    # Process items
    items = list(range(20))
    results = await pipeline.run(items)

    print(f"Processed {len(results)} items")
    for result in results[:5]:
        print(f"  ID {result['id']}: {result['value']}")

asyncio.run(main())
```

**Output:**
```
Processed 20 items
  ID 0: saved_DATA_0
  ID 1: saved_DATA_1
  ID 2: saved_DATA_2
  ID 3: saved_DATA_3
  ID 4: saved_DATA_4
```

### Pipeline with Status Tracking

Monitor pipeline execution with StatusTracker:

```python
from antflow import Pipeline, Stage, StatusTracker

async def on_status_change(event):
    if event.status == "completed":
        print(f"✅ Completed item {event.item_id}")
    elif event.status == "failed":
        print(f"❌ Failed item {event.item_id}: {event.metadata.get('error')}")

tracker = StatusTracker(on_status_change=on_status_change)

stage = Stage(
    name="ProcessStage",
    workers=3,
    tasks=[process_data],
    retry="per_task",
    task_attempts=3
)

pipeline = Pipeline(stages=[stage], status_tracker=tracker)
results = await pipeline.run(items)

# Query statistics
stats = tracker.get_stats()
print(f"Completed: {stats['completed']}, Failed: {stats['failed']}")
```

### Getting Pipeline Statistics

Monitor pipeline progress:

```python
import asyncio
from antflow import Pipeline, Stage

async def main():
    pipeline = Pipeline(stages=[extract_stage, transform_stage])
    results = await pipeline.run(range(100))

    # Get statistics
    stats = pipeline.get_stats()
    print(f"Items processed: {stats.items_processed}")
    print(f"Items failed: {stats.items_failed}")
    print(f"Items in-flight: {stats.items_in_flight}")
    print(f"Queue sizes: {stats.queue_sizes}")

asyncio.run(main())
```

**Output:**
```
Items processed: 200
Items failed: 0
Items in-flight: 0
Queue sizes: {'Extract': 0, 'Transform': 0}
```

## Complete Basic Example

Here's a complete working example combining executor and pipeline:

```python
import asyncio
from antflow import AsyncExecutor, Pipeline, Stage

# Executor example
async def double(x):
    await asyncio.sleep(0.1)
    return x * 2

# Pipeline example
async def fetch(x):
    return f"item_{x}"

async def process(x):
    return x.upper()

async def main():
    # Use executor for quick parallel processing
    print("=== AsyncExecutor ===")
    async with AsyncExecutor(max_workers=5) as executor:
        results = await executor.map(double, range(5))
        print(f"Executor results: {results}")

    # Use pipeline for multi-stage processing
    print("\n=== Pipeline ===")
    stage1 = Stage(name="Fetch", workers=3, tasks=[fetch])
    stage2 = Stage(name="Process", workers=2, tasks=[process])

    pipeline = Pipeline(stages=[stage1, stage2])
    results = await pipeline.run(range(5))

    print(f"Pipeline results:")
    for r in results:
        print(f"  {r['id']}: {r['value']}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
=== AsyncExecutor ===
Executor results: [0, 2, 4, 6, 8]

=== Pipeline ===
Pipeline results:
  0: ITEM_0
  1: ITEM_1
  2: ITEM_2
  3: ITEM_3
  4: ITEM_4
```

## Next Steps

- Explore [Advanced Examples](advanced.md) for more complex use cases
- Read the [AsyncExecutor Guide](../user-guide/executor.md) for detailed documentation
- Learn about [Pipeline](../user-guide/pipeline.md) features and patterns
- Check the [API Reference](../api/index.md) for complete documentation
