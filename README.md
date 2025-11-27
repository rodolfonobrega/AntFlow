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
- [Types](docs/api/types.md) - Type definitions
- [Utils](docs/api/utils.md) - Utility functions

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