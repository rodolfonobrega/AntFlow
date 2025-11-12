"""
Simple worker monitoring example showing state and metrics queries.
"""

import asyncio

from antflow import Pipeline, Stage


async def slow_task(x: int) -> int:
    """Task with variable processing time."""
    await asyncio.sleep(0.05 + (x % 5) * 0.02)
    return x * 2


async def monitor_workers(pipeline: Pipeline):
    """Monitor worker states in real-time."""
    while True:
        await asyncio.sleep(0.5)

        states = pipeline.get_worker_states()
        metrics = pipeline.get_worker_metrics()
        stats = pipeline.get_stats()

        busy_count = sum(1 for s in states.values() if s.status == "busy")

        print(f"\r[Monitor] Active: {busy_count}/{len(states)} | "
              f"Processed: {stats.items_processed} | "
              f"Failed: {stats.items_failed} | "
              f"In flight: {stats.items_in_flight}", end="", flush=True)

        if stats.items_in_flight == 0 and busy_count == 0:
            break

    print()


async def main():
    print("=== Worker Monitoring Example ===\n")

    stage = Stage(
        name="Process",
        workers=5,
        tasks=[slow_task]
    )

    pipeline = Pipeline(stages=[stage])

    print(f"Workers: {pipeline.get_worker_names()}\n")

    items = list(range(30))

    monitor_task = asyncio.create_task(monitor_workers(pipeline))

    print("Processing items...")
    results = await pipeline.run(items)

    await monitor_task

    print(f"\n{'='*60}")
    print("Final Results")
    print(f"{'='*60}\n")

    print(f"✅ Processed {len(results)} items\n")

    print("Worker States:")
    for name, state in pipeline.get_worker_states().items():
        print(f"  {name}: {state.status}")

    print("\nWorker Metrics:")
    for name, metric in sorted(pipeline.get_worker_metrics().items()):
        print(
            f"  {name}: "
            f"{metric.items_processed} items, "
            f"avg {metric.avg_processing_time:.3f}s"
        )

    snapshot = pipeline.get_dashboard_snapshot()
    print(f"\nSnapshot timestamp: {snapshot.timestamp:.2f}")
    print(f"Total workers: {len(snapshot.worker_states)}")
    print(f"Total processed: {snapshot.pipeline_stats.items_processed}")


if __name__ == "__main__":
    asyncio.run(main())
