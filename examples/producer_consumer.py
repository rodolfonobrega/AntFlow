
import asyncio
import random
import time
from typing import AsyncIterable

from antflow import Pipeline, Stage

# --- 1. The Producer ---
# This simulates a "data generator" that creates items over time.
# Perhaps it's reading from a stream, a websocket, or generating calculations.
async def data_producer(count: int = 10) -> AsyncIterable[int]:
    print(f"[Producer] Starting to generate {count} items...")
    for i in range(count):
        # Simulate work to generate data (e.g., fetching from API)
        delay = random.uniform(0.1, 0.5)
        await asyncio.sleep(delay)
        
        print(f"[Producer] Generated item {i}")
        yield i

    print("[Producer] Done generating items.")


# --- 2. The Consumer (Worker Task) ---
# This is the work that will be done by the workers in parallel.
async def process_data(item: int) -> str:
    # Simulate processing time
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)
    
    result = f"processed_{item}"
    print(f"  [Worker] Finished {result} (took {delay:.2f}s)")
    return result


async def main():
    print("=== Producer-Consumer Example ===\n")
    print("In this example, the pipeline starts with workers idle.")
    print("Data is 'fed' into the pipeline asynchronously as it is generated.\n")

    # Define the Consumer Stage
    # User requested "2 workers"
    worker_stage = Stage(
        name="Processor",
        workers=2,
        tasks=[process_data],
        retry="per_task",
        task_attempts=3
    )

    # Initialize Pipeline
    pipeline = Pipeline(
        stages=[worker_stage],
        collect_results=True  # Collect results to show at the end
    )

    # --- KEY PART: Manually controlling the lifecycle ---
    
    # 1. Start the workers. They will sit idle, waiting for work.
    print("Step 1: Starting pipeline (workers are idle)...")
    await pipeline.start()
    
    # 2. Feed data from our async generator.
    # The pipeline will consume items as they are yielded by the producer.
    print("Step 2: Feeding data from producer...")
    await pipeline.feed_async(data_producer(10))

    # 3. Wait for everything to finish.
    print("Step 3: Waiting for pipeline to drain...")
    await pipeline.join()

    # --- Summary ---
    print("\n=== Done! ===")
    print(f"Total processed: {len(pipeline.results)}")
    print(f"Stats: {pipeline.get_stats()}")
    
    print("\nFirst 3 results:")
    for res in pipeline.results[:3]:
        print(f" - {res.value}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
