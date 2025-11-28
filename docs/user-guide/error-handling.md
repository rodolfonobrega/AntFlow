# Error Handling

AntFlow provides a robust error handling system with custom exceptions and flexible retry strategies.

## Exception Hierarchy

AntFlow defines a clear exception hierarchy for different error scenarios:

```python
AntFlowError                    # Base exception
├── ExecutorShutdownError         # Executor has been shut down
├── PipelineError                 # Pipeline-specific errors
│   └── StageValidationError      # Invalid stage configuration
└── TaskFailedError               # Task execution failure
```

## Exception Types

### AntFlowError

Base exception for all AntFlow errors:

```python
from antflow import AntFlowError

try:
    # AntFlow operations
    pass
except AntFlowError as e:
    print(f"AntFlow error: {e}")
```

### ExecutorShutdownError

Raised when attempting to use a shut down executor:

```python
from antflow import AsyncExecutor, ExecutorShutdownError

executor = AsyncExecutor(max_workers=5)
await executor.shutdown()

try:
    executor.submit(some_task, arg)
except ExecutorShutdownError:
    print("Cannot submit to shutdown executor")
```

### PipelineError

Base exception for pipeline-specific errors:

```python
from antflow import Pipeline, PipelineError

try:
    # Example: Attempting invalid operation
    raise PipelineError("Cannot modify pipeline while running")
except PipelineError as e:
    print(f"Pipeline error: {e}")
```



### StageValidationError

Raised when stage configuration is invalid:

```python
from antflow import Stage, StageValidationError

try:
    stage = Stage(
        name="Invalid",
        workers=0,  # Invalid: must be >= 1
        tasks=[my_task]
    )
    stage.validate()
except StageValidationError as e:
    print(f"Invalid stage: {e}")
```

### TaskFailedError

Wrapper for task failures that preserves the original exception:

```python
from antflow import TaskFailedError

# The original exception is available
try:
    # ... task execution
    pass
except TaskFailedError as e:
    print(f"Task {e.task_name} failed")
    print(f"Original error: {e.original_exception}")
```

## Handling Task Failures

### In AsyncExecutor

Exceptions in executor tasks are propagated to the caller:

```python
from antflow import AsyncExecutor

async def failing_task(x):
    if x < 0:
        raise ValueError("Negative value not allowed")
    return x * 2

async with AsyncExecutor(max_workers=3) as executor:
    future = executor.submit(failing_task, -5)

    try:
        result = await future.result()
    except ValueError as e:
        print(f"Task failed: {e}")
        # Handle the error appropriately
```

### In Pipeline

Pipeline provides multiple ways to handle failures:

#### Stage-Level Callbacks

```python
from antflow import Stage

async def on_failure(payload):
    item_id = payload['id']
    error = payload['error']
    print(f"Stage failed for item {item_id}: {error}")
    # Log to monitoring system, send alert, etc.

stage = Stage(
    name="ProcessStage",
    workers=3,
    tasks=[risky_task],
    on_failure=on_failure
)
```

#### Task-Level Callbacks

```python
from antflow import Stage

async def on_task_failure(task_name, item_id, error):
    print(f"Task {task_name} failed for item {item_id}")
    print(f"Error: {error}")
    # Record failure for analysis

stage = Stage(
    name="DetailedStage",
    workers=2,
    tasks=[task1, task2],
    on_task_failure=on_task_failure
)
```

#### Collecting Failed Items

```python
from antflow import Pipeline, Stage

failed_items = []

async def collect_failures(payload):
    failed_items.append({
        'id': payload['id'],
        'error': payload['error'],
        'stage': payload['stage']
    })

stage = Stage(
    name="MyStage",
    workers=3,
    tasks=[my_task],
    retry="per_task",
    task_attempts=3,
    on_failure=collect_failures
)

pipeline = Pipeline(stages=[stage])
results = await pipeline.run(items)

# Analyze failures
print(f"Succeeded: {len(results)}")
print(f"Failed: {len(failed_items)}")
for failed in failed_items:
    print(f"  Item {failed['id']}: {failed['error']}")
```

## Retry Strategies

AntFlow provides two retry strategies for pipelines:

### Per-Task Retry

Each task retries independently using tenacity:

```python
from antflow import Stage

stage = Stage(
    name="RobustStage",
    workers=5,
    tasks=[api_call],
    retry="per_task",
    task_attempts=5,
    task_wait_seconds=2.0
)
```

If a task fails after all retries, the stage fails for that item.

### Per-Stage Retry

The entire stage retries on any task failure:

```python
from antflow import Stage

stage = Stage(
    name="TransactionalStage",
    workers=2,
    tasks=[begin_tx, update_data, commit_tx],
    retry="per_stage",
    stage_attempts=3
)
```

Failed items are re-queued at the beginning of the stage.

## Extracting Original Exceptions

AntFlow automatically extracts original exceptions from retry wrappers:

```python
from antflow.utils import extract_exception
from tenacity import RetryError

# In callbacks, errors are already extracted
async def on_failure(payload):
    error = payload['error']  # Already the original exception message
    print(f"Original error: {error}")

# Manual extraction if needed
try:
    # ... operation with retry
    pass
except RetryError as e:
    original = extract_exception(e)
    print(f"Original exception: {original}")
```

## Best Practices

### 1. Use Specific Exceptions

Catch specific exceptions rather than broad Exception types:

```python
from antflow import AsyncExecutor, ExecutorShutdownError
import logging

logger = logging.getLogger(__name__)

try:
    result = await executor.submit(task, arg)
except ExecutorShutdownError:
    # Handle shutdown specifically
    logger.warning("Executor was shut down")
except ValueError:
    # Handle validation errors
    logger.error("Invalid input")
except Exception as e:
    # Catch-all for unexpected errors
    logger.exception("Unexpected error", exc_info=e)
```

### 2. Always Set Failure Callbacks

In production, always configure failure callbacks:

```python
from antflow import Stage
import logging

logger = logging.getLogger(__name__)

async def log_failure(payload):
    logger.error(
        "Stage failure",
        extra={
            'item_id': payload['id'],
            'stage': payload['stage'],
            'error': payload['error']
        }
    )

stage = Stage(
    name="ProductionStage",
    workers=10,
    tasks=[process],
    on_failure=log_failure
)
```

### 3. Configure Appropriate Retries

Choose retry strategies based on your use case:

- **Idempotent operations**: Use per-task retry with high attempts
- **Transactional operations**: Use per-stage retry
- **External APIs**: Use longer wait times between retries

```python
from antflow import Stage

# For external API calls
api_stage = Stage(
    name="API",
    workers=5,
    tasks=[call_api],
    retry="per_task",
    task_attempts=5,
    task_wait_seconds=3.0
)

# For transactional database operations
db_stage = Stage(
    name="Database",
    workers=2,
    tasks=[begin_tx, insert, update, commit],
    retry="per_stage",
    stage_attempts=3
)
```

### 4. Monitor Failure Rates

Track failures to identify issues:

```python
stats = pipeline.get_stats()
failure_rate = stats.items_failed / (stats.items_processed + stats.items_failed)

if failure_rate > 0.1:  # More than 10% failures
    logger.warning(f"High failure rate: {failure_rate:.2%}")
    # Alert, adjust retry settings, etc.
```

### 5. Graceful Degradation

Handle failures gracefully without stopping the entire pipeline:

```python
from antflow import Pipeline

async def on_failure(payload):
    # Log the failure
    logger.error(f"Item {payload['id']} failed: {payload['error']}")

    # Store for later retry
    await failed_queue.put(payload)

    # Update metrics
    metrics.increment('pipeline.failures')

# Pipeline continues processing other items
pipeline = Pipeline(stages=[stage])
results = await pipeline.run(items)

# Process failures separately
await retry_failed_items(failed_queue)
```

## Example: Robust ETL Pipeline

Here's a complete example with comprehensive error handling:

```python
import asyncio
import logging
from antflow import Pipeline, Stage

logger = logging.getLogger(__name__)

# Track failures
failures = []

async def on_stage_failure(payload):
    failures.append(payload)
    logger.error(
        f"Stage {payload['stage']} failed for item {payload['id']}: "
        f"{payload['error']}"
    )

async def on_task_retry(task_name, item_id, error):
    logger.warning(f"Retrying {task_name} for item {item_id}: {error}")

async def fetch_data(item_id):
    # May fail due to network issues
    ...

async def validate_data(data):
    # May fail due to invalid data
    if not data.get('required_field'):
        raise ValueError("Missing required field")
    return data

async def save_data(data):
    # May fail due to database issues
    ...

async def main():
    # Fetch stage: retry on network errors
    fetch_stage = Stage(
        name="Fetch",
        workers=10,
        tasks=[fetch_data],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=2.0,
        on_failure=on_stage_failure,
        on_task_retry=on_task_retry
    )

    # Validate stage: don't retry validation errors
    validate_stage = Stage(
        name="Validate",
        workers=5,
        tasks=[validate_data],
        retry="per_task",
        task_attempts=1,
        on_failure=on_stage_failure
    )

    # Save stage: retry on transient database errors
    save_stage = Stage(
        name="Save",
        workers=3,
        tasks=[save_data],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=3.0,
        on_failure=on_stage_failure,
        on_task_retry=on_task_retry
    )

    pipeline = Pipeline(
        stages=[fetch_stage, validate_stage, save_stage]
    )

    items = range(100)
    results = await pipeline.run(items)

    # Report results
    stats = pipeline.get_stats()
    logger.info(f"Processed: {stats.items_processed}")
    logger.info(f"Failed: {stats.items_failed}")
    logger.info(f"Success rate: {stats.items_processed/len(items)*100:.1f}%")

    # Handle failures
    if failures:
        logger.warning(f"{len(failures)} items require manual intervention")
        for failure in failures:
            # Store in dead letter queue, send alert, etc.
            await handle_permanent_failure(failure)

asyncio.run(main())
```

## Debugging Tips

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('antflow')
logger.setLevel(logging.DEBUG)
```

### Use Task-Level Callbacks

Get detailed information about task execution:

```python
import logging
from antflow import Stage

logger = logging.getLogger(__name__)

async def on_task_start(task_name, item_id, value):
    logger.debug(f"Starting {task_name} for item {item_id}")

async def on_task_failure(task_name, item_id, error):
    logger.error(f"Task {task_name} failed for item {item_id}: {error}")
    # Include stack trace in logs
    logger.exception("Full traceback:", exc_info=error)

stage = Stage(
    name="Debug",
    workers=1,
    tasks=[task],
    on_task_start=on_task_start,
    on_task_failure=on_task_failure
)
```

### Check Pipeline Stats

Monitor pipeline health during execution:

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

async def monitor_pipeline(pipeline):
    while True:
        stats = pipeline.get_stats()
        logger.info(
            f"Progress: {stats.items_processed} processed, "
            f"{stats.items_failed} failed, "
            f"{stats.items_in_flight} in-flight"
        )
        await asyncio.sleep(5.0)

# Run monitoring concurrently with pipeline
async with asyncio.TaskGroup() as tg:
    tg.create_task(monitor_pipeline(pipeline))
    results = await pipeline.run(items)
```
