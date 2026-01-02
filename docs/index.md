# AntFlow

**Stop waiting for the slowest task. Start processing smarter.**

<p align="center">
  <img src="images/antflow-workers.png" alt="AntFlow Worker Pool Concept" width="600">
</p>

AntFlow is a modern async execution library for Python that solves a fundamental problem in batch processing: **the slowest task bottleneck**.

## The Problem

When processing batches of async tasks (API calls, file operations, database queries), traditional approaches wait for ALL tasks in a batch to complete before starting the next batch:

```python
# Traditional approach - inefficient
for batch in chunks(items, 10):
    await asyncio.gather(*[process(item) for item in batch])
    # 🐌 Wait for ALL 10 to finish, even if 9 are done
```

**The bottleneck**: If 9 tasks complete in 1 minute but 1 task takes 30 minutes, you waste 29 minutes of potential processing time.

## The Solution

AntFlow uses **independent worker pools** where workers continuously grab new tasks as soon as they finish:

```python
# AntFlow approach - efficient
stage = Stage(name="Process", workers=10, tasks=[process])
pipeline = Pipeline(stages=[stage])
await pipeline.run(items)
# ✨ Workers never wait - always processing
```

**The benefit**: As soon as any worker finishes, it picks the next task. Zero idle time. Maximum throughput.

---

## Real-World Example

Processing 1000 batches through OpenAI's Batch API:

### Before AntFlow
- Process 10 batches at a time
- Wait for all 10 to complete
- 1 slow batch = entire group waits
- **Total time: 6+ hours** ⏰

### After AntFlow
- 10 workers process continuously
- Slow batches don't block fast ones
- Automatic retry on failures
- **Total time: 2 hours** ⚡

**Result: 3x faster processing with better reliability**

---

## Quick Start

### Installation

```bash
pip install antflow
```

### Simple Example

```python
import asyncio
from antflow import Pipeline, Stage

async def fetch_data(item_id):
    # Your async operation
    return f"data_{item_id}"

async def process_data(data):
    # Your processing logic
    return data.upper()

async def main():
    # Define pipeline stages
    fetch_stage = Stage(name="Fetch", workers=10, tasks=[fetch_data])
    process_stage = Stage(name="Process", workers=5, tasks=[process_data])

    # Create pipeline
    pipeline = Pipeline(stages=[fetch_stage, process_stage])

    # Process 100 items
    results = await pipeline.run(range(100))
    print(f"Processed {len(results)} items")

asyncio.run(main())
```

---

## Key Features

### 🚀 **Worker Pool Architecture**
Independent workers that never block each other, ensuring optimal resource utilization.

### 🔄 **Multi-Stage Pipelines**
Chain operations with configurable worker pools per stage for complex ETL workflows.

### 💪 **Built-in Resilience**
Per-task and per-stage retry strategies with exponential backoff handle transient failures automatically.

### 📊 **Real-time Monitoring**
StatusTracker for real-time item tracking with event-driven monitoring and statistics.

### 👷 **Worker-Level Tracking**
Track which specific worker processes each item with unique worker IDs and custom item IDs.

### 🎯 **Familiar API**
Drop-in async replacement for `concurrent.futures` with `submit()`, `map()`, and `as_completed()`.

### 🔧 **Type Safe**
Full type hints throughout for better IDE support and fewer bugs.

---

## Use Cases

AntFlow is **perfect** for:

- **Batch API Processing** - OpenAI, Anthropic, AWS, any batch API
- **ETL Pipelines** - Extract, transform, load data at scale
- **Web Scraping** - Fetch, parse, and store web data efficiently
- **Data Processing** - Process large datasets with retry logic
- **Microservices** - Chain async service calls with error handling
- **Batch Operations** - Any scenario where you process many items asynchronously

---

## Core Concepts

### AsyncExecutor

Similar to `concurrent.futures.ThreadPoolExecutor` but for async operations:

```python
import asyncio
from antflow import AsyncExecutor

async def process(x):
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    async with AsyncExecutor(max_workers=10) as executor:
        results = await executor.map(process, range(100))
        print(results)

asyncio.run(main())
```

### Pipeline Stages

Build multi-stage workflows with independent worker pools:

```python
from antflow import Pipeline, Stage

# Different worker counts optimized for each stage
fetch_stage = Stage(name="Fetch", workers=10, tasks=[fetch])      # I/O bound
process_stage = Stage(name="Process", workers=5, tasks=[process]) # CPU bound
save_stage = Stage(name="Save", workers=3, tasks=[save])          # Rate limited

pipeline = Pipeline(stages=[fetch_stage, process_stage, save_stage])
```

### Retry Strategies

**Per-Task Retry** (independent operations):
```python
stage = Stage(
    name="APICall",
    workers=10,
    tasks=[call_api],
    retry="per_task",
    task_attempts=5,
    task_wait=2.0
)
```

**Per-Stage Retry** (transactional operations):
```python
stage = Stage(
    name="Transaction",
    workers=3,
    tasks=[begin_tx, update_db, commit_tx],
    retry="per_stage",
    stage_attempts=3
)
```

---

## Getting Started

Choose your learning path:

<div class="grid cards" markdown>

-   **New to AntFlow?**

    [Quick Start Guide →](getting-started/quickstart.md)

-   **From concurrent.futures?**

    [AsyncExecutor Guide →](user-guide/executor.md)

-   **Building pipelines?**

    [Pipeline Guide →](user-guide/pipeline.md)

-   **Ready to dive deep?**

    [API Reference →](api/index.md)

</div>

---

## Requirements

- Python 3.9+
- tenacity >= 8.0.0

---

## Why AntFlow?

AntFlow was born from a real production problem: processing thousands of batches through OpenAI's API. Traditional batch processing wasted hours waiting for slow tasks to complete.

The solution? **Independent workers that never wait.**

When a worker finishes a task, it immediately grabs the next one. No coordination overhead. No bottlenecks. Just continuous, efficient processing.

If you're processing data through APIs, building ETL pipelines, or running any kind of batch async operations, AntFlow will save you time.

**Start processing smarter, not harder.** 🚀

---

## Links

- **GitHub**: [github.com/rodolfonobrega/antflow](https://github.com/rodolfonobrega/antflow)
- **PyPI**: [pypi.org/project/antflow](https://pypi.org/project/antflow)
- **Issues**: [Report a bug](https://github.com/rodolfonobrega/antflow/issues)

---

## License

AntFlow is released under the [MIT License](https://github.com/rodolfonobrega/antflow/blob/main/LICENSE).

<p align="center">
  <em>Made with ❤️ to solve real problems in production</em>
</p>
