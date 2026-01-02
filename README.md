<p align="center">
  <img src="docs/images/antflow-logo.png" alt="AntFlow Logo" width="800">
</p>

# AntFlow

## Why AntFlow?

The name 'AntFlow' is inspired by the efficiency of an ant colony, where each ant (worker) performs its specialized function, and together they contribute to the colony's collective goal. Similarly, AntFlow orchestrates independent workers to achieve complex asynchronous tasks seamlessly.

### The Problem I Had to Solve

I was processing massive amounts of data using OpenAI's Batch API. The workflow was complex:

1. Upload batches of data to OpenAI
2. Wait for processing to complete
3. Download the results
4. Save to database
5. Repeat for the next batch

Initially, I processed 10 batches at a time using basic async. But here's the problem: **I had to wait for ALL 10 batches to complete before starting the next group.**

### The Bottleneck

Imagine this scenario:

- 9 batches complete in 5 minutes
- 1 batch gets stuck and takes 30 minutes
- **I waste 25 minutes waiting for that one slow batch while my system sits idle**

With hundreds of batches to process, these delays accumulated into **hours of wasted time**. Even worse, one failed batch would block the entire pipeline.

### The Solution: AntFlow

I built AntFlow to solve this exact problem. Instead of batch-by-batch processing, AntFlow uses worker pools where:

- ✅ Each worker handles tasks independently
- ✅ When a worker finishes, it immediately grabs the next task
- ✅ Slow tasks don't block fast ones
- ✅ Always maintain optimal concurrency (e.g., 10 tasks running simultaneously)
- ✅ Built-in retry logic for failed tasks
- ✅ Multi-stage pipelines for complex workflows

**Result:** My OpenAI batch processing went from taking hours to completing in a fraction of the time, with automatic retry handling and zero idle time.

<p align="center">
  <img src="docs/images/antflow-workers.png" alt="AntFlow Workers" width="600">
</p>

<p align="center">
  <em>AntFlow: Modern async execution library with concurrent.futures-style API and advanced pipelines</em>
</p>

---

## Key Features

### 🚀 **Worker Pool Architecture**
- Independent workers that never block each other
- Automatic task distribution
- Optimal resource utilization

### 🔄 **Multi-Stage Pipelines**
- Chain operations with configurable worker pools per stage
- Each stage runs independently
- Data flows automatically between stages
- **Priority Queues**: Assign priority to items to bypass sequential processing (NEW)
- **Interactive Control**: Resume pipelines and inject items into any stage (NEW)

### 💪 **Built-in Resilience**
- Per-task retry with exponential backoff
- Per-stage retry for transactional operations
- Failed tasks don't stop the pipeline

### 📊 **Real-time Monitoring & Dashboards**
- **Worker State Tracking** - Know what each worker is doing in real-time
- **Performance Metrics** - Track items processed, failures, avg time per worker
- **Task-Level Events** - Monitor individual task retries and failures
- **Dashboard API** - Query snapshots for live dashboards and UIs
- **Event Streaming** - Subscribe to status changes via callbacks
- **StatusTracker** - Real-time item tracking with full history
- **PipelineDashboard** - Helper for combining queries and events

### 🎯 **Familiar API**
- Drop-in async replacement for `concurrent.futures`
- `submit()`, `map()`, `as_completed()` methods
- Clean, intuitive interface

---

## Use Cases

### ✅ **Perfect for:**
- **Batch API Processing** - OpenAI, Anthropic, any batch API
- **ETL Pipelines** - Extract, transform, load at scale
- **Web Scraping** - Fetch, parse, store web data efficiently
- **Data Processing** - Process large datasets with retry logic
- **Microservices** - Chain async service calls with error handling

### ⚡ **Real-world Impact:**
- Process large batches without bottlenecks
- Automatic retry for transient failures
- Zero idle time = maximum throughput
- Clear observability with metrics and callbacks

---

## Quick Install

```bash
pip install antflow
```

---

## Quick Example

```python
import asyncio
from antflow import Pipeline, Stage

# Your actual work
async def upload_batch(batch_data):
    # Upload to OpenAI API
    return "batch_id"

async def check_status(batch_id):
    # Check if batch is ready
    return "result_url"

async def download_results(result_url):
    # Download processed data
    return "processed_data"

async def save_to_db(processed_data):
    # Save results
    return "saved"

# Build the pipeline
upload_stage = Stage(name="Upload", workers=10, tasks=[upload_batch])
check_stage = Stage(name="Check", workers=10, tasks=[check_status])
download_stage = Stage(name="Download", workers=10, tasks=[download_results])
save_stage = Stage(name="Save", workers=5, tasks=[save_to_db])

pipeline = Pipeline(stages=[upload_stage, check_stage, download_stage, save_stage])

# Process batches efficiently
batches = ["batch1", "batch2", "batch3"]
results = await pipeline.run(batches)
```

**What happens**: Each stage has its own worker pool (10 for Upload, 10 for Check, 10 for Download, 5 for Save). Workers in each stage process tasks independently. As soon as a worker finishes, it picks the next task. No waiting. No idle time. Maximum throughput.

---

## Core Concepts

### AsyncExecutor: Simple Concurrent Execution

For straightforward parallel processing, AsyncExecutor provides a `concurrent.futures`-style API:

```python
import asyncio
from antflow import AsyncExecutor

async def process_item(x):
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    async with AsyncExecutor(max_workers=10) as executor:
        # Using map() - returns list directly (like list(executor.map(...)) in concurrent.futures)
        # retries=3 means it will try up to 4 times total with exponential backoff
        results = await executor.map(process_item, range(100), retries=3)
        print(f"Processed {len(results)} items")

asyncio.run(main())
```

### Pipeline: Multi-Stage Processing

For complex workflows with multiple steps, you can build a `Pipeline`:

```python
import asyncio
from antflow import Pipeline, Stage

async def fetch(x):
    await asyncio.sleep(0.1)
    return f"data_{x}"

async def process(x):
    await asyncio.sleep(0.1)
    return x.upper()

async def save(x):
    await asyncio.sleep(0.1)
    return f"saved_{x}"

async def main():
    # Define stages with different worker counts
    fetch_stage = Stage(name="Fetch",        workers=5,
        tasks=[fetch_data, process_data],
        # Limit specific tasks to avoid rate limits
        task_concurrency_limits={
            "fetch_data": 2  # Only 2 concurrent fetch_data calls
        }
    )
    process_stage = Stage(name="Process", workers=5, tasks=[process_data])
    save_stage = Stage(name="Save", workers=3, tasks=[save])

    # Build pipeline
    pipeline = Pipeline(stages=[fetch_stage, process_stage, save_stage])

    # Process 100 items through all stages
    results = await pipeline.run(range(100))

    print(f"Completed: {len(results)} items")
    print(f"Stats: {pipeline.get_stats()}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Why different worker counts?**
- **Fetch**: I/O bound, use more workers (10)
- **Process**: CPU bound, moderate workers (5)
- **Save**: Rate-limited API, fewer workers (3)

---

## Real-Time Monitoring with StatusTracker

Track every item as it flows through your pipeline with **StatusTracker**. Get real-time status updates, query current states, and access complete event history.

```python
from antflow import Pipeline, Stage, StatusTracker
import asyncio

# Mock tasks
async def fetch(x): return x
async def process(x): return x * 2
async def save(x): return x

# 1. Define a callback for real-time updates
async def log_event(event):
    print(f"Item {event.item_id}: {event.status} @ {event.stage}")

tracker = StatusTracker(on_status_change=log_event)

# Define stages
stage1 = Stage(name="Fetch", workers=5, tasks=[fetch])
stage2 = Stage(name="Process", workers=3, tasks=[process])
stage3 = Stage(name="Save", workers=5, tasks=[save])

pipeline = Pipeline(
    stages=[stage1, stage2, stage3],
    status_tracker=tracker
)

# 2. Run pipeline (logs will print in real-time)
async def main():
    items = range(50)
    results = await pipeline.run(items)

    # 3. Get final statistics
    stats = tracker.get_stats()
    print(f"Completed: {stats['completed']}")
    print(f"Failed: {stats['failed']}")

    # Get full history for an item
    history = tracker.get_history(item_id=0)

asyncio.run(main())
```

See the [examples/](examples/) directory for more advanced usage, including a **Rich Dashboard** example (`examples/rich_polling_dashboard.py`).

---

## Documentation

AntFlow has comprehensive documentation to help you get started and master advanced features:

### 🚀 Getting Started
- [Quick Start Guide](https://rodolfonobrega.github.io/antflow/getting-started/quickstart/) - Get up and running in minutes
- [Installation Guide](https://rodolfonobrega.github.io/antflow/getting-started/installation/) - Installation instructions

### 📚 User Guides
- [AsyncExecutor Guide](https://rodolfonobrega.github.io/antflow/user-guide/executor/) - Using the concurrent.futures-style API
- [Concurrency Control](https://rodolfonobrega.github.io/antflow/user-guide/concurrency/) - Managing concurrency limits and semaphores
- [Pipeline Guide](https://rodolfonobrega.github.io/antflow/user-guide/pipeline/) - Building multi-stage workflows
- [Dashboard Guide](https://rodolfonobrega.github.io/antflow/user-guide/dashboard/) - Real-time monitoring and dashboards
- [Error Handling](https://rodolfonobrega.github.io/antflow/user-guide/error-handling/) - Managing failures and retries
- [Worker Tracking](https://rodolfonobrega.github.io/antflow/user-guide/worker-tracking/) - Monitoring individual workers

### 💡 Examples
- [Examples Index](https://rodolfonobrega.github.io/antflow/examples/) - **Start Here**: List of all 11+ example scripts
- [Basic Examples](https://rodolfonobrega.github.io/antflow/examples/basic/) - Simple use cases to get started
- [Advanced Examples](https://rodolfonobrega.github.io/antflow/examples/advanced/) - Complex workflows and patterns

### 📖 API Reference
- [API Index](https://rodolfonobrega.github.io/antflow/api/) - Complete API documentation
- [AsyncExecutor](https://rodolfonobrega.github.io/antflow/api/executor/) - Executor API reference
- [Pipeline](https://rodolfonobrega.github.io/antflow/api/pipeline/) - Pipeline API reference
- [StatusTracker](https://rodolfonobrega.github.io/antflow/api/tracker/) - Status tracking and monitoring
- [Exceptions](https://rodolfonobrega.github.io/antflow/api/exceptions/) - Exception types
- [Types](https://rodolfonobrega.github.io/antflow/api/types/) - Type definitions
- [Utils](https://rodolfonobrega.github.io/antflow/api/utils/) - Utility functions

You can also build and serve the documentation locally using `mkdocs`:

```bash
pip install mkdocs-material
mkdocs serve
```
Then open your browser to `http://127.0.0.1:8000`.

---

## Requirements

- Python 3.9+
- tenacity >= 8.0.0

**Note**: For Python 3.9-3.10, the `taskgroup` backport is automatically installed.

---

## Running Tests

To run the test suite, first install the development dependencies from the project root:

```bash
pip install -e ".[dev]"
```

Then, you can run the tests using `pytest`:

```bash
pytest
```

---

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md).

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ to solve real problems in production
</p>
