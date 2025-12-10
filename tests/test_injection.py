
import asyncio
import pytest
from antflow.pipeline import Pipeline, Stage

# --- Helper Tasks ---
async def append_tag(x, tag):
    return f"{x}_{tag}"

async def task_a(x): return await append_tag(x, "A")
async def task_b(x): return await append_tag(x, "B")
async def task_c(x): return await append_tag(x, "C")

@pytest.mark.asyncio
async def test_injection_logic():
    """
    Verify that items injected into specific stages skip previous stages.
    Flow: A -> B -> C
    """
    stage_a = Stage("StageA", 1, [task_a])
    stage_b = Stage("StageB", 1, [task_b])
    stage_c = Stage("StageC", 1, [task_c])
    
    pipeline = Pipeline([stage_a, stage_b, stage_c])
    
    await pipeline.start()
    
    # 1. Normal Feed (StageA -> B -> C)
    # input "1" -> "1_A_B_C"
    await pipeline.feed(["1"], target_stage="StageA")
    
    # 2. Inject Middle (StageB -> C)
    # input "2" -> "2_B_C" (Skipped A)
    await pipeline.feed(["2"], target_stage="StageB")
    
    # 3. Inject Last (StageC only)
    # input "3" -> "3_C" (Skipped A and B)
    await pipeline.feed(["3"], target_stage="StageC")
    
    await pipeline.join()
    
    results = sorted(pipeline.results, key=lambda r: r.value)
    values = [r.value for r in results]
    
    print(f"Results: {values}")
    
    assert "1_A_B_C" in values
    assert "2_B_C" in values
    assert "3_C" in values
    assert len(values) == 3

@pytest.mark.asyncio
async def test_invalid_target_stage():
    """Verify error raises when targeting non-existent stage."""
    stage = Stage("OnlyStage", 1, [task_a])
    pipeline = Pipeline([stage])
    
    with pytest.raises(ValueError) as exc:
        await pipeline.feed(["fail"], target_stage="GhostStage")
    
    assert "not found" in str(exc.value)

@pytest.mark.asyncio
async def test_default_target_is_first_stage():
    """Verify that omitting target_stage targets the first stage."""
    stage_a = Stage("First", 1, [task_a])
    stage_b = Stage("Second", 1, [task_b])
    
    pipeline = Pipeline([stage_a, stage_b])
    await pipeline.start()
    
    await pipeline.feed(["start"]) # Should go to First
    await pipeline.join()
    
    assert pipeline.results[0].value == "start_A_B"

if __name__ == "__main__":
    asyncio.run(test_injection_logic())
    asyncio.run(test_invalid_target_stage())
    asyncio.run(test_default_target_is_first_stage())
    print("All injection tests passed!")
