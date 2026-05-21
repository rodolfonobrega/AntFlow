# AntFlow

AntFlow is an async Python library for concurrent task execution and multi-stage pipelines.

## Skills

- `/antflow` — Full guide with examples for using the AntFlow library (AsyncExecutor, Pipeline, Stage, StatusTracker)

## Project Structure

```
antflow/          # Core package
  executor.py     # AsyncExecutor implementation
  pipeline.py     # Pipeline, Stage, PipelineBuilder
  tracker.py      # StatusTracker and event types
  types.py        # PipelineResult, WorkerState, TaskEvent, StatusEvent
  exceptions.py   # AntFlowError hierarchy
  display/        # Dashboard implementations (compact, detailed, full)
  context.py      # set_task_status helper
examples/         # 20+ working examples
tests/            # pytest test suite
docs/             # MkDocs documentation
```

## Key Conventions

- Python 3.9+, async/await throughout
- Tasks are plain `async def` functions — no decorators needed
- `AsyncExecutor` for simple parallel execution (like `concurrent.futures`)
- `Pipeline + Stage` for multi-stage ETL/processing workflows
- Tests use `pytest-asyncio`; run with `pytest tests/`
