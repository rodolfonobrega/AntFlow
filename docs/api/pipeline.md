# Pipeline API

The `antflow.pipeline` module provides the core functionality for building and running multi-stage asynchronous workflows.

## Overview

A **Pipeline** consists of a sequence of **Stages**. Each stage has its own pool of workers and processes items independently. Data flows from one stage to the next automatically.

Key components:

- **[Pipeline][antflow.pipeline.Pipeline]**: The main orchestrator that manages stages and data flow.
- **[Stage][antflow.pipeline.Stage]**: Configuration for a single processing step, including worker count and retry logic.

## Usage Example

```python
import asyncio
from antflow import Pipeline, Stage

async def fetch_data(url):
    # ... fetch logic ...
    return data

async def process_data(data):
    # ... process logic ...
    return result

async def main():
    # Define stages
    stage1 = Stage(name="Fetch", workers=5, tasks=[fetch_data])
    stage2 = Stage(name="Process", workers=2, tasks=[process_data])

    # Create pipeline
    pipeline = Pipeline(stages=[stage1, stage2])

    # Run
    urls = ["http://example.com/1", "http://example.com/2"]
    results = await pipeline.run(urls)
```

## Configuration Reference

### Stage Configuration

When creating a `Stage`, you can configure its behavior extensively:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Unique name for the stage. |
| `workers` | `int` | Required | Number of concurrent workers for this stage. |
| `tasks` | `List[Callable]` | Required | List of async functions to execute in order. |
| `retry` | `str` | `"per_task"` | Retry strategy: `"per_task"` (retry individual functions) or `"per_stage"` (retry entire stage). |
| `task_attempts` | `int` | `3` | Max attempts for a single task (used with `per_task`). |
| `stage_attempts` | `int` | `3` | Max attempts for the whole stage (used with `per_stage`). |
| `task_wait_seconds` | `float` | `1.0` | Wait time between retries. |
| `unpack_args` | `bool` | `False` | If `True`, unpacks tuple/dict inputs as `*args` and `**kwargs` for the task function. |

### Pipeline Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stages` | `List[Stage]` | Required | Ordered list of stages. |
| `collect_results` | `bool` | `True` | If `True`, accumulates results in memory. Set to `False` for streaming-only workflows to save memory. |
| `status_tracker` | `StatusTracker` | `None` | Optional tracker for real-time monitoring. |

## Class Reference

For complete class definitions, see the [source code](../../antflow/pipeline.py).
