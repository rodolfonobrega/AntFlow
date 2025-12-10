
import asyncio
import pytest
from antflow.pipeline import Pipeline, Stage

async def passthrough(x):
    await asyncio.sleep(0.01) # Yield to let priority queue sorting happen if backed up
    return x

@pytest.mark.asyncio
async def test_priority_ordering():
    """Verify that lower priority values are processed first."""
    stage = Stage("StageA", 1, [passthrough]) 
    pipeline = Pipeline([stage])
    
    await pipeline.start()
    
    # 1. Feed a "blocker" first (normal priority)
    # This ensures the worker is busy while we queue the rest
    await pipeline.feed(["blocker"], priority=100)
    # Give worker time to pick up blocker so it's "in progress"
    await asyncio.sleep(0.05)
    
    # 2. Feed mixed priorities
    await pipeline.feed(["low"], priority=500)
    await pipeline.feed(["medium"], priority=100)
    await pipeline.feed(["high"], priority=10)
    await pipeline.feed(["critical"], priority=0)
    
    await pipeline.join()
    
    # Check raw execution order
    raw_results = [r.value for r in pipeline._results]
    print(f"Raw completion order: {raw_results}")
    
    # "blocker" runs first (it was alone).
    # Then the queue contained [low, medium, high, critical].
    # Sorted by priority: critical(0), high(10), medium(100), low(500).
    
    assert raw_results[0] == "blocker"
    assert raw_results[1] == "critical"
    assert raw_results[2] == "high"
    assert raw_results[3] == "medium"
    assert raw_results[4] == "low"

@pytest.mark.asyncio
async def test_fifo_stability():
    """Verify FIFO order for same priority."""
    stage = Stage("StageA", 1, [passthrough]) 
    pipeline = Pipeline([stage])
    
    await pipeline.start()
    
    # Occupy worker
    await pipeline.feed(["blocker"], priority=10)
    
    # Queue same priority
    await pipeline.feed(["A"], priority=100)
    await pipeline.feed(["B"], priority=100)
    await pipeline.feed(["C"], priority=100)
    
    await pipeline.join()
    
    raw_results = [r.value for r in pipeline._results]
    # filter out blocker
    res = [x for x in raw_results if x != "blocker"]
    
    assert res == ["A", "B", "C"]

if __name__ == "__main__":
    asyncio.run(test_priority_ordering())
    asyncio.run(test_fifo_stability())
    print("Priority tests passed!")
