# Quick Start

Get started with AntFlow in minutes!

## AsyncExecutor Example

The `AsyncExecutor` provides a familiar `concurrent.futures`-style API for async operations:

```python
import asyncio
from antflow import AsyncExecutor

async def process_item(x):
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    async with AsyncExecutor(max_workers=5) as executor:
        # Map over items - returns list directly
        results = await executor.map(process_item, range(10))
        print(results)  # [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

asyncio.run(main())
```

## Pipeline Example

Create multi-stage processing pipelines with ease:

```python
import asyncio
from antflow import Pipeline, Stage

async def fetch(x):
    return f"data_{x}"

async def process(x):
    return x.upper()

async def main():
    # Define stages
    stage1 = Stage(name="Fetch", workers=3, tasks=[fetch])
    stage2 = Stage(name="Process", workers=2, tasks=[process])

    # Create and run pipeline
    pipeline = Pipeline(stages=[stage1, stage2])
    results = await pipeline.run(range(10))
    print(results)

asyncio.run(main())
```

## Key Concepts

### AsyncExecutor

Similar to `concurrent.futures.ThreadPoolExecutor` but for async operations:

- **`submit(fn, *args, **kwargs)`** - Submit a single async task
- **`map(fn, *iterables)`** - Map function over iterables, returns list
- **`map_iter(fn, *iterables)`** - Map function over iterables, yields results (async iterator)
- **`as_completed(futures)`** - Iterate over futures as they complete

### Pipeline

Multi-stage processing with configurable workers and retry strategies:

- **Stages** - Define processing steps with worker pools
- **Tasks** - Sequence of async functions per stage
- **Retry Strategies** - Per-task or per-stage retry logic
- **StatusTracker** - Real-time monitoring with event callbacks
- **Worker Tracking** - Track which worker processes each item with custom item IDs

## Next Steps

- Explore the [AsyncExecutor Guide](../user-guide/executor.md) for detailed usage
- Learn about [Pipeline](../user-guide/pipeline.md) features and patterns
- See [Worker Tracking](../user-guide/worker-tracking.md) for monitoring individual workers
- Check out [Examples](../examples/basic.md) for real-world use cases
- Browse the [API Reference](../api/index.md) for complete documentation
