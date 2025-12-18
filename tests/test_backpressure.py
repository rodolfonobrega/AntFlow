import asyncio
import pytest
from antflow import Pipeline, Stage

async def noop(x):
    return x

@pytest.mark.asyncio
async def test_smart_queue_defaults():
    """Test that queues get correct default sizes based on worker count."""
    # Case 1: 1 worker -> 10 capacity
    stage1 = Stage("S1", workers=1, tasks=[noop])
    # Case 2: 5 workers -> 50 capacity
    stage2 = Stage("S2", workers=5, tasks=[noop])
    
    pipeline = Pipeline(stages=[stage1, stage2])
    
    # Internal queue access for verification
    # Note: This relies on internal implementation details (_queues)
    assert pipeline._queues[0].maxsize == 10
    assert pipeline._queues[1].maxsize == 50

@pytest.mark.asyncio
async def test_explicit_queue_capacity():
    """Test that explicit queue_capacity overrides defaults."""
    stage = Stage("S1", workers=2, tasks=[noop], queue_capacity=100)
    pipeline = Pipeline(stages=[stage])
    
    assert pipeline._queues[0].maxsize == 100

@pytest.mark.asyncio
async def test_backpressure_blocking():
    """
    Test that the pipeline actually blocks when the queue is full.
    We'll fill a small queue and assert that the next put operation blocks/times out.
    """
    # Create a stage with capacity=2 and a slow consumer
    # We won't start the pipeline workers, so items will just sit in the queue.
    stage = Stage("S1", workers=1, tasks=[noop], queue_capacity=2)
    pipeline = Pipeline(stages=[stage])
    
    # Fill the queue (capacity 2)
    # The PriorityQueue logic might depend on how we feed
    # pipeline.feed puts into _queues[0]
    
    await pipeline.feed([1, 2])
    
    # The queue should now be full (size 2)
    assert pipeline._queues[0].qsize() == 2
    assert pipeline._queues[0].full()
    
    # Trying to feed one more item should timeout because the queue is full
    # and no workers are consuming it.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(pipeline.feed([3]), timeout=0.2)

@pytest.mark.asyncio
async def test_backpressure_propagation():
    """
    Test end-to-end backpressure propagation.
    Fast producer stage -> Slow consumer stage.
    """
    async def slow_task(x):
        # Hold the item for a short time
        await asyncio.sleep(0.05)
        return x

    # Stage 2 has capacity 2 and 1 worker.
    # It effectively holds 1 item in process + 2 in queue = 3 items max.
    stage1 = Stage("Producer", workers=1, tasks=[noop])
    stage2 = Stage("Consumer", workers=1, tasks=[slow_task], queue_capacity=2)
    
    pipeline = Pipeline(stages=[stage1, stage2])
    
    items = list(range(10))
    await pipeline.run(items)
    
    stats = pipeline.get_stats()
    print(f"\nStats: {stats}")
    
    # Verify we got results
    assert len(pipeline.results) == 10, f"Expected 10 results, got {len(pipeline.results)}. Stats: {stats}"
