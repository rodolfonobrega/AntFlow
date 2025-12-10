
import asyncio
import time
from antflow import Pipeline, Stage

async def slow_task(item):
    """Simulates a task that takes time, allowing queue to build up."""
    # Simulate processing time
    await asyncio.sleep(0.1) 
    return f"Processed {item}"

async def main():
    # Only 1 worker to strictly force queuing and demonstrate priority sorting
    stage = Stage("Processing", workers=1, tasks=[slow_task])
    pipeline = Pipeline([stage])

    await pipeline.start()

    print("--- Feeding Blocker ---")
    # Feed a blocker to occupy the worker
    await pipeline.feed([{"id": "blocker", "value": "BLOCKER"}], priority=100)
    
    # Allow worker to pick it up
    await asyncio.sleep(0.05)

    print("--- Feeding Mixed Priorities ---")
    # Feed items with different priorities
    # They will sit in queue while "blocker" is finishing
    
    # Low Priority (500)
    await pipeline.feed([{"id": "low", "value": "LowPrio"}], priority=500)
    print("Fed Low (500)")
    
    # Normal Priority (100)
    await pipeline.feed([{"id": "norm", "value": "NormalPrio"}], priority=100)
    print("Fed Normal (100)")
    
    # High Priority (10) - Should jump ahead of Low and Normal
    await pipeline.feed([{"id": "high", "value": "HighPrio"}], priority=10)
    print("Fed High (10)")
    
    # Critical Priority (0) - Should jump to very front
    await pipeline.feed([{"id": "crit", "value": "CRITICAL"}], priority=0)
    print("Fed Critical (0)")

    print("--- Waiting for results ---")
    await pipeline.join()

    # To see the processing order, we look at the raw results list 
    # (since pipeline.results is sorted by input sequence ID)
    raw_results = [r.value for r in pipeline._results]
    
    print("\nProcessing Order:")
    for res in raw_results:
        print(f" -> {res}")

if __name__ == "__main__":
    asyncio.run(main())
