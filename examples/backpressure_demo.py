"""
Backpressure demonstration example.

Shows how the pipeline handles backpressure when a slow consumer
cannot keep up with a fast producer. The queue between stages
has a limited capacity, causing the producer to block when full.

Key concepts:
- Fast producer stage generates items quickly
- Slow consumer stage processes items slowly
- Queue capacity limits prevent memory overflow
- Backpressure automatically throttles the producer
"""

import asyncio

from antflow import Pipeline, Stage, StatusTracker


async def fast_generator(x: int) -> int:
    """Fast producer that generates items quickly."""
    await asyncio.sleep(0.01)
    return x


async def slow_consumer(x: int) -> int:
    """Slow consumer that processes items slowly."""
    await asyncio.sleep(0.5)
    return x * 2


async def monitor_pipeline(pipeline: Pipeline, tracker: StatusTracker):
    """Monitor queue sizes and worker states in real-time."""
    print("\nStarting Monitoring...")

    while True:
        await asyncio.sleep(0.5)

        stats = pipeline.get_stats()
        worker_states = pipeline.get_worker_states()

        consumer_queue_size = stats.queue_sizes.get("Consumer", 0)

        gen_states = [s for n, s in worker_states.items() if "Generator" in n]
        busy_generators = sum(1 for s in gen_states if s.status == "busy")

        print(
            f"Consumer Queue: {consumer_queue_size:2d} | "
            f"Generator Busy: {busy_generators} | "
            f"Processed: {stats.items_processed} | "
            f"In Flight: {stats.items_in_flight}"
        )

        if consumer_queue_size >= 9:
            print(">>> BACKPRESSURE: Queue nearly full, generator likely blocked")

        if stats.items_in_flight == 0 and stats.items_processed > 0:
            break


async def main():
    print("=" * 60)
    print("Backpressure Demonstration")
    print("=" * 60)
    print()
    print("Configuration:")
    print("  - Generator: 1 worker, 0.01s per item (fast)")
    print("  - Consumer: 1 worker, 0.5s per item (slow)")
    print("  - Queue capacity: ~10 items (workers * 10)")
    print()
    print("Expected behavior:")
    print("  - Generator produces items faster than Consumer can process")
    print("  - Queue fills up to capacity (~10 items)")
    print("  - Generator blocks until Consumer frees queue space")
    print()

    tracker = StatusTracker()

    generator_stage = Stage(
        name="Generator",
        workers=1,
        tasks=[fast_generator]
    )

    consumer_stage = Stage(
        name="Consumer",
        workers=1,
        tasks=[slow_consumer]
    )

    pipeline = Pipeline(
        stages=[generator_stage, consumer_stage],
        status_tracker=tracker
    )

    monitor_task = asyncio.create_task(monitor_pipeline(pipeline, tracker))

    print("Feeding 20 items...")
    results = await pipeline.run(range(20))

    await monitor_task

    print()
    print("=" * 60)
    print(f"✅ Finished. Processed {len(results)} items.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
