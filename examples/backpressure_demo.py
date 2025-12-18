import asyncio
import time
from antflow import Pipeline, Stage, StatusTracker

async def fast_generator(x):
    # Produces items very quickly
    await asyncio.sleep(0.01)
    return x

async def slow_consumer(x):
    # Consumes items slowly
    await asyncio.sleep(0.5)
    return x * 2

async def monitor_queues(pipeline):
    print("\nStarting Monitoring...")
    while True:
        await asyncio.sleep(0.5)
        # Access internal queues to check sizes
        # Queue 0: Input for Stage 1 (Generator)
        # Queue 1: Input for Stage 2 (Consumer)
        
        q1_size = pipeline._queues[1].qsize()
        
        # Check generator workers status
        gen_states = [s for n, s in pipeline.get_worker_states().items() if "Generator" in n]
        busy_gen = sum(1 for s in gen_states if s.status == "busy")
        
        print(f"Time: {time.time():.1f} | Consumer Queue: {q1_size} | Generator Workers Busy: {busy_gen}")
        
        if q1_size >= 10:
            print(">>> BACKPRESSURE DETECTED: Queue is full (limit ~10). Generator should be blocked.")

async def main():
    tracker = StatusTracker()
    
    # Stage 1: Generator
    # 1 Worker -> Implicit Capacity = 10
    stage1 = Stage("Generator", workers=1, tasks=[fast_generator])
    
    # Stage 2: Consumer
    # 1 Worker -> Implicit Capacity = 10 (But its own output queue doesn't matter much here)
    # The important part is stage1 trying to push to stage2's input queue.
    stage2 = Stage("Consumer", workers=1, tasks=[slow_consumer])
    
    pipeline = Pipeline(stages=[stage1, stage2], status_tracker=tracker)
    
    # Start monitor
    asyncio.create_task(monitor_queues(pipeline))
    
    print("Feeding 50 items...")
    # Feed 50 items. 
    # Stage 1 will process them fast.
    # Stage 2 queue has capacity ~10.
    # So Stage 1 should be blocked after pushing ~10 items to Stage 2.
    results = await pipeline.run(range(50))
    print(f"\nFinished. Processed {len(results)} items.")

if __name__ == "__main__":
    asyncio.run(main())
