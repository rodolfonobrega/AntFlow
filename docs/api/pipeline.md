# Pipeline Module

The pipeline module provides multi-stage async processing with configurable retry strategies and callbacks.

## Overview

A `Pipeline` consists of multiple `Stage`s. Each stage has its own worker pool and processes items independently.
Items flow from one stage to the next automatically.

### Key Features

- **Worker Pools**: Each stage has a dedicated number of workers.
- **Retry Logic**: Configurable retry attempts per task or per stage.
- **Argument Unpacking**: Support for unpacking tuple/dict arguments into task function parameters.
- **Monitoring**: Integration with `StatusTracker` for real-time visibility.

## Stage

The `Stage` class defines a processing step in the pipeline.

### Configuration

- `name`: Unique name for the stage.
- `workers`: Number of concurrent workers.
- `tasks`: List of async functions to execute in order.
- `retry`: Retry strategy ("per_task" or "per_stage").
- `unpack_args`: If `True`, unpacks input items (tuples/dicts) as arguments for the task function.

::: antflow.pipeline.Stage
    options:
      show_root_heading: true
      show_source: false
      members_order: source

## Pipeline

The `Pipeline` class orchestrates the execution of stages.

::: antflow.pipeline.Pipeline
    options:
      show_root_heading: true
      show_source: false
      members_order: source
