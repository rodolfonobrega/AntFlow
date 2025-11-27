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



## Class Reference

### Stage

::: antflow.pipeline.Stage
    options:
      show_root_heading: true
      show_source: false
      members_order: source

### Pipeline

::: antflow.pipeline.Pipeline
    options:
      show_root_heading: true
      show_source: false
      members_order: source
