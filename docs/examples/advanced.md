# Advanced Examples

Complex real-world examples demonstrating advanced AntFlow features.

## Pipeline with Retry Strategies

This example shows different retry strategies for handling failures:

```python
import asyncio
import random
from antflow import Pipeline, Stage

# Tasks that may fail
async def fetch_api_data(item_id: int) -> dict:
    """Simulate fetching data from an API (may fail randomly)."""
    await asyncio.sleep(0.05)
    if random.random() < 0.2:
        raise ConnectionError(f"API connection failed for item {item_id}")
    return {"id": item_id, "data": f"raw_data_{item_id}"}

async def validate_data(data: dict) -> dict:
    """Validate fetched data."""
    await asyncio.sleep(0.03)
    if "data" not in data:
        raise ValueError("Invalid data structure")
    data["validated"] = True
    return data

async def save_to_database(data: dict) -> dict:
    """Simulate saving to database (may fail randomly)."""
    await asyncio.sleep(0.06)
    if random.random() < 0.15:
        raise IOError(f"Database write failed for item {data['id']}")
    data["saved"] = True
    return data

# Callbacks for monitoring
async def on_fetch_success(payload):
    print(f"  ✅ Fetched item {payload['id']}")

async def on_fetch_failure(payload):
    print(f"  ❌ Failed to fetch item {payload['id']}: {payload['error']}")

async def on_fetch_retry(payload):
    print(f"  🔄 Retrying fetch for item {payload['id']} (attempt {payload['attempt']})")

async def on_save_task_retry(task_name, item_id, error):
    print(f"  🔄 Task {task_name} retrying for item {item_id}: {error}")

async def on_save_task_failure(task_name, item_id, error):
    print(f"  ❌ Task {task_name} failed for item {item_id}: {error}")

async def main():
    # Fetch stage: per-stage retry for connection errors
    fetch_stage = Stage(
        name="Fetch",
        workers=3,
        tasks=[fetch_api_data],
        retry="per_stage",
        stage_attempts=3
    )

    # Process stage: per-task retry for validation
    process_stage = Stage(
        name="Process",
        workers=2,
        tasks=[validate_data],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=0.5
    )

    # Save stage: per-task retry
    save_stage = Stage(
        name="Save",
        workers=2,
        tasks=[save_to_database],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=1.0
    )

    pipeline = Pipeline(
        stages=[fetch_stage, process_stage, save_stage]
    )

    items = list(range(15))
    results = await pipeline.run(items)

    stats = pipeline.get_stats()
    print(f"\n📊 Statistics:")
    print(f"  Items processed: {stats.items_processed}")
    print(f"  Items failed: {stats.items_failed}")
    print(f"  Success rate: {stats.items_processed/(stats.items_processed + stats.items_failed)*100:.1f}%")

asyncio.run(main())
```

**Key Features:**
- Per-stage retry for connection errors (transient failures)
- Per-task retry for database writes
- Comprehensive callbacks for monitoring
- Statistics reporting

## Real-World ETL Pipeline

Complete ETL example with data processing, validation, and error handling:

```python
import asyncio
import random
from typing import Any, Dict
from antflow import Pipeline, Stage

class DataProcessor:
    """Example data processor with realistic ETL operations."""

    async def fetch_user_data(self, user_id: int) -> Dict[str, Any]:
        """Fetch user data from external API."""
        await asyncio.sleep(0.1)

        if random.random() < 0.1:
            raise ConnectionError(f"Failed to fetch user {user_id}")

        return {
            "user_id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
            "created_at": "2025-01-01"
        }

    async def validate_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user data structure and content."""
        await asyncio.sleep(0.05)

        required_fields = ["user_id", "name", "email"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        if "@" not in data["email"]:
            raise ValueError(f"Invalid email: {data['email']}")

        data["validated"] = True
        return data

    async def transform_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data to target format."""
        await asyncio.sleep(0.05)

        return {
            "id": data["user_id"],
            "full_name": data["name"].upper(),
            "email_address": data["email"].lower(),
            "registration_date": data["created_at"],
            "status": "active"
        }

    async def enrich_with_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich data with additional metadata."""
        await asyncio.sleep(0.08)

        data["metadata"] = {
            "processed_at": "2025-10-09",
            "version": "1.0",
            "source": "api"
        }

        return data

    async def calculate_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate user metrics."""
        await asyncio.sleep(0.06)

        data["metrics"] = {
            "score": random.randint(1, 100),
            "rank": random.choice(["bronze", "silver", "gold"]),
            "engagement": random.uniform(0, 1)
        }

        return data

    async def save_to_database(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save processed data to database."""
        await asyncio.sleep(0.1)

        if random.random() < 0.05:
            raise IOError(f"Database write failed for user {data['id']}")

        data["saved"] = True
        data["db_id"] = f"db_{data['id']}"

        return data

async def on_stage_complete(payload):
    stage = payload.get("stage", "Unknown")
    user_id = payload.get("id", "?")
    print(f"  [{stage}] Completed processing user {user_id}")

async def on_stage_failed(payload):
    stage = payload.get("stage", "Unknown")
    user_id = payload.get("id", "?")
    error = payload.get("error", "Unknown error")
    print(f"  [{stage}] ❌ Failed for user {user_id}: {error}")

async def main():
    print("=" * 60)
    print("Real-World ETL Pipeline: User Data Processing")
    print("=" * 60)
    print()

    processor = DataProcessor()

    # Ingestion stage with high concurrency and retry
    ingestion_stage = Stage(
        name="Ingestion",
        workers=5,
        tasks=[processor.fetch_user_data],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=1.0,
        on_success=on_stage_complete,
        on_failure=on_stage_failed
    )

    # Validation and transformation
    validation_stage = Stage(
        name="Validation",
        workers=3,
        tasks=[processor.validate_user_data, processor.transform_user_data],
        retry="per_task",
        task_attempts=2,
        task_wait_seconds=0.5,
        on_success=on_stage_complete,
        on_failure=on_stage_failed
    )

    # Data enrichment
    enrichment_stage = Stage(
        name="Enrichment",
        workers=3,
        tasks=[processor.enrich_with_metadata, processor.calculate_metrics],
        retry="per_stage",
        stage_attempts=2,
        on_success=on_stage_complete,
        on_failure=on_stage_failed
    )

    # Database persistence
    persistence_stage = Stage(
        name="Persistence",
        workers=2,
        tasks=[processor.save_to_database],
        retry="per_task",
        task_attempts=5,
        task_wait_seconds=2.0
    )

    pipeline = Pipeline(
        stages=[ingestion_stage, validation_stage, enrichment_stage, persistence_stage],
        collect_results=True
    )

    user_ids = list(range(1, 51))

    print(f"📥 Starting ETL pipeline for {len(user_ids)} users")
    print(f"📊 Pipeline configuration:")
    for stage in pipeline.stages:
        print(f"  - {stage.name}: {stage.workers} workers, "
              f"{len(stage.tasks)} tasks, retry={stage.retry}")
    print()

    results = await pipeline.run(user_ids)

    print()
    print("=" * 60)
    print("Pipeline Execution Complete")
    print("=" * 60)
    print()

    stats = pipeline.get_stats()

    print("📊 Final Statistics:")
    print(f"  Total items: {len(user_ids)}")
    print(f"  Successfully processed: {stats.items_processed}")
    print(f"  Failed: {stats.items_failed}")
    print(f"  Success rate: {stats.items_processed/len(user_ids)*100:.1f}%")

    if results:
        print(f"\n✅ Successfully processed {len(results)} users")
        print("\nSample output (first 3 users):")
        for result in results[:3]:
            data = result['value']
            print(f"\n  User ID: {data['id']}")
            print(f"  Name: {data['full_name']}")
            print(f"  Email: {data['email_address']}")
            print(f"  Metrics: Score={data['metrics']['score']}, "
                  f"Rank={data['metrics']['rank']}")

if __name__ == "__main__":
    random.seed(42)  # For reproducible results
    asyncio.run(main())
```

**Key Features:**
- Complete ETL workflow with 4 stages
- Class-based organization for related operations
- Different retry strategies per stage
- Comprehensive error handling and monitoring
- Statistics and reporting

## Monitoring Pipeline Execution

Real-time monitoring of pipeline progress:

```python
import asyncio
from antflow import Pipeline, Stage

async def task1(x): return x + 1
async def task2(x): return x * 2

async def monitor_pipeline(pipeline, interval=1.0):
    """Monitor pipeline execution in real-time."""
    while True:
        stats = pipeline.get_stats()
        print(
            f"📊 Progress: {stats.items_processed} processed, "
            f"{stats.items_failed} failed, "
            f"{stats.items_in_flight} in-flight"
        )
        await asyncio.sleep(interval)

async def main():
    # Define your pipeline stages
    stage1 = Stage(name="Stage1", workers=5, tasks=[task1])
    stage2 = Stage(name="Stage2", workers=3, tasks=[task2])

    pipeline = Pipeline(stages=[stage1, stage2])
    items = range(100)

    # Run monitoring and pipeline concurrently
    async with asyncio.TaskGroup() as tg:
        # Start monitoring
        monitor_task = tg.create_task(monitor_pipeline(pipeline, interval=0.1))

        # Run pipeline
        results = await pipeline.run(items)

        # Stop monitoring
        monitor_task.cancel()

    print(f"Completed: {len(results)} items")

if __name__ == "__main__":
    asyncio.run(main())
```



## Collecting and Analyzing Failures

Track failed items for retry or analysis:

```python
import asyncio
import random
from antflow import Pipeline, Stage

class FailureCollector:
    def __init__(self):
        self.failures = []

    async def on_failure(self, item_id, error, metadata):
        self.failures.append({
            'id': item_id,
            'error': str(error),
            'metadata': metadata
        })

async def risky_task(x):
    if random.random() < 0.5:
        raise ValueError("Random failure")
    return x

async def main():
    collector = FailureCollector()
    items = range(10)

    stage = Stage(
        name="ProcessStage",
        workers=5,
        tasks=[risky_task],
        retry="per_task",
        task_attempts=3,
        on_failure=collector.on_failure
    )

    pipeline = Pipeline(stages=[stage])
    results = await pipeline.run(items)

    # Analyze failures
    print(f"Success: {len(results)} items")
    print(f"Failures: {len(collector.failures)} items")

    if collector.failures:
        print("\nFailed items:")
        for failure in collector.failures:
            print(f"  ID {failure['id']}: {failure['error']}")

        # Retry failed items with different configuration
        retry_stage = Stage(
            name="Retry",
            workers=2,
            tasks=[risky_task],
            retry="per_task",
            task_attempts=10,
            task_wait_seconds=0.1
        )

        retry_pipeline = Pipeline(stages=[retry_stage])
        # In a real scenario, you'd extract the original values to retry
        retry_items = [f['id'] for f in collector.failures] 
        retry_results = await retry_pipeline.run(retry_items)

        print(f"\nRetry results: {len(retry_results)} recovered")

if __name__ == "__main__":
    asyncio.run(main())
```

## Context Manager with Cleanup

Use context managers for automatic resource cleanup:

```python
import asyncio
from antflow import Pipeline, Stage

async def task(x): return x

async def main():
    stage1 = Stage(name="S1", workers=1, tasks=[task])
    stage2 = Stage(name="S2", workers=1, tasks=[task])
    stage3 = Stage(name="S3", workers=1, tasks=[task])
    items = range(5)

    async with Pipeline(stages=[stage1, stage2, stage3]) as pipeline:
        # Pipeline runs and automatically cleans up
        results = await pipeline.run(items)

        # Do something with results
        print(f"Processed {len(results)} items")

    # Pipeline is automatically shut down here
    print("Pipeline cleaned up")

if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- Review the [Error Handling Guide](../user-guide/error-handling.md) for comprehensive error strategies
- Check the [API Reference](../api/index.md) for detailed class documentation
- Explore the [User Guide](../user-guide/executor.md) for in-depth feature explanations
