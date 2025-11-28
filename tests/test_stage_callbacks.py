import asyncio
import pytest
from antflow import Pipeline, Stage

@pytest.mark.asyncio
async def test_stage_callbacks_success():
    """Test that on_success callback is invoked."""
    success_events = []

    async def on_success(item_id, result, metadata):
        success_events.append((item_id, result))

    async def task(x):
        return x * 2

    stage = Stage(
        name="Stage1",
        workers=1,
        tasks=[task],
        on_success=on_success
    )

    pipeline = Pipeline(stages=[stage])
    await pipeline.run([1, 2])

    assert len(success_events) == 2
    assert (0, 2) in success_events
    assert (1, 4) in success_events

@pytest.mark.asyncio
async def test_stage_callbacks_failure():
    """Test that on_failure callback is invoked."""
    failure_events = []

    async def on_failure(item_id, error, metadata):
        failure_events.append((item_id, str(error)))

    async def failing_task(x):
        raise ValueError("Fail")

    stage = Stage(
        name="Stage1",
        workers=1,
        tasks=[failing_task],
        retry="per_task",
        task_attempts=1,
        on_failure=on_failure
    )

    pipeline = Pipeline(stages=[stage])
    await pipeline.run([1])

    assert len(failure_events) == 1
    assert failure_events[0][0] == 0
    assert "Fail" in failure_events[0][1]

@pytest.mark.asyncio
async def test_sync_callbacks():
    """Test that synchronous callbacks work."""
    events = []

    def on_success(item_id, result, metadata):
        events.append(result)

    async def task(x):
        return x

    stage = Stage(
        name="Stage1",
        workers=1,
        tasks=[task],
        on_success=on_success
    )

    pipeline = Pipeline(stages=[stage])
    await pipeline.run([1])

    assert len(events) == 1
    assert events[0] == 1
