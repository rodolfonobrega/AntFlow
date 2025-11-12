"""
Real-world ETL example: Processing user data from an API.

Scenario: Fetch user data from an API, validate and transform it,
enrich with additional data, and save to a database.
"""

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

        transformed = {
            "id": data["user_id"],
            "full_name": data["name"].upper(),
            "email_address": data["email"].lower(),
            "registration_date": data["created_at"],
            "status": "active"
        }

        return transformed

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
    """Callback when a stage completes."""
    stage = payload.get("stage", "Unknown")
    user_id = payload.get("id", "?")
    print(f"  [{stage}] Completed processing user {user_id}")


async def on_stage_failed(payload):
    """Callback when a stage fails."""
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

    ingestion_stage = Stage(
        name="Ingestion",
        workers=5,
        tasks=[processor.fetch_user_data],
        retry="per_task",
        task_attempts=3,
        task_wait_seconds=1.0
    )

    validation_stage = Stage(
        name="Validation",
        workers=3,
        tasks=[processor.validate_user_data, processor.transform_user_data],
        retry="per_task",
        task_attempts=2,
        task_wait_seconds=0.5
    )

    enrichment_stage = Stage(
        name="Enrichment",
        workers=3,
        tasks=[processor.enrich_with_metadata, processor.calculate_metrics],
        retry="per_stage",
        stage_attempts=2
    )

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
    print("📊 Pipeline configuration:")
    for stage in pipeline.stages:
        print(f"  - {stage.name}: {stage.workers} workers, "
              f"{len(stage.tasks)} tasks, retry={stage.retry}")
    print()

    print("Processing...")
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
    print()

    if results:
        print(f"✅ Successfully processed {len(results)} users")
        print()
        print("Sample output (first 3 users):")
        for result in results[:3]:
            data = result['value']
            print(f"\n  User ID: {data['id']}")
            print(f"  Name: {data['full_name']}")
            print(f"  Email: {data['email_address']}")
            print(f"  Metrics: Score={data['metrics']['score']}, "
                  f"Rank={data['metrics']['rank']}")
            print(f"  Database ID: {data['db_id']}")

    print()
    print("Pipeline stats:", stats)


if __name__ == "__main__":
    random.seed(42)
    asyncio.run(main())
