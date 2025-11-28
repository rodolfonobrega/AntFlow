import pytest
import asyncio
from antflow import Pipeline, Stage, StatusTracker
from antflow.types import StatusEvent

async def failing_task(x):
    if x == "fail":
        raise ValueError("Intentional failure")
    return x

@pytest.mark.asyncio
async def test_retry_status_emission():
    events = []
    
    async def on_status_change(event: StatusEvent):
        events.append(event)

    tracker = StatusTracker(on_status_change=on_status_change)
    
    # Configure stage with per_stage retry
    stage = Stage(
        name="TestStage",
        workers=1,
        tasks=[failing_task],
        retry="per_stage",
        stage_attempts=2,
        task_wait_seconds=0.1
    )
    
    pipeline = Pipeline(stages=[stage], status_tracker=tracker)
    
    # Run with a failing item
    await pipeline.run([{"id": 1, "value": "fail"}])
    
    # Check for 'retrying' status
    retry_events = [e for e in events if e.status == "retrying"]
    assert len(retry_events) > 0, "Should have emitted at least one 'retrying' event"
    
    # Verify metadata
    first_retry = retry_events[0]
    assert first_retry.metadata.get("retry") is True
    assert first_retry.metadata.get("attempt") == 2
    assert "Intentional failure" in first_retry.metadata.get("error")
