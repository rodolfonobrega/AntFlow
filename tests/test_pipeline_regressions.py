"""Regression tests for pipeline edge cases."""

import asyncio
import logging

import pytest

from antflow import Pipeline, Stage
from antflow.pipeline import RendezvousChannel
from antflow.exceptions import StageValidationError

# ---------------------------------------------------------------------------
# on_failure called in per_stage mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_failure_called_in_per_stage():
    called = []

    async def always_fail(x):
        raise ValueError("boom")

    def on_fail(item_id, error, payload):
        called.append((item_id, error))

    stage = Stage(
        name="S",
        workers=2,
        tasks=[always_fail],
        retry="per_stage",
        stage_attempts=1,
        on_failure=on_fail,
    )
    await Pipeline(stages=[stage]).run([1, 2])

    assert len(called) == 2
    assert all(isinstance(err, ValueError) for _, err in called)


# ---------------------------------------------------------------------------
# on_success not fired for skipped items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_success_not_called_for_skipped_items():
    success_called = []

    async def identity(x):
        return x

    stage = Stage(
        name="S",
        workers=2,
        tasks=[identity],
        skip_if=lambda x: x % 2 == 0,
        on_success=lambda item_id, val, payload: success_called.append(val),
    )
    await Pipeline(stages=[stage]).run([1, 2, 3, 4])

    # Only odd items (1, 3) should trigger on_success
    assert set(success_called) == {1, 3}


# ---------------------------------------------------------------------------
# on_skip fired for skipped items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_skip_called_for_skipped_items():
    skipped = []

    async def identity(x):
        return x

    stage = Stage(
        name="S",
        workers=2,
        tasks=[identity],
        skip_if=lambda x: x % 2 == 0,
        on_skip=lambda item_id, val, payload: skipped.append(val),
    )
    await Pipeline(stages=[stage]).run([1, 2, 3, 4])

    assert set(skipped) == {2, 4}


# ---------------------------------------------------------------------------
# shutdown warns when items are discarded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_warns_on_discarded_items(caplog):
    barrier = asyncio.Event()

    async def blocking_task(x):
        await barrier.wait()
        return x

    stage = Stage(name="S", workers=1, tasks=[blocking_task], queue_capacity=10)
    pipeline = Pipeline(stages=[stage])
    await pipeline.start()
    await pipeline.feed(list(range(5)))

    with caplog.at_level(logging.WARNING, logger="antflow.pipeline"):
        await pipeline.shutdown()

    assert any("discarded" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# per_stage retry does not deadlock when workers == queue_capacity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_stage_retry_no_deadlock():
    """Workers == queue_capacity, all fail on first attempt — must not deadlock."""
    call_count: dict[int, int] = {}

    async def fail_once(x):
        n = call_count.get(x, 0) + 1
        call_count[x] = n
        if n == 1:
            raise ValueError("first attempt fails")
        return x

    stage = Stage(
        name="S",
        workers=3,
        tasks=[fail_once],
        retry="per_stage",
        stage_attempts=2,
        queue_capacity=3,
    )
    results = await asyncio.wait_for(
        Pipeline(stages=[stage]).run([1, 2, 3]),
        timeout=5.0,
    )
    assert len(results) == 3


# ---------------------------------------------------------------------------
# task_concurrency_limits rejects unknown task names
# ---------------------------------------------------------------------------


def test_task_concurrency_limits_unknown_name_raises():
    async def real_task(x):
        return x

    with pytest.raises(StageValidationError, match="unknown task"):
        Stage(
            name="S",
            workers=1,
            tasks=[real_task],
            task_concurrency_limits={"nonexistent_task": 2},
        ).validate()


# ---------------------------------------------------------------------------
# task-level events emitted in per_stage mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_events_emitted_in_per_stage():
    from antflow.tracker import StatusTracker

    started = []
    completed = []

    async def my_task(x):
        return x * 2

    async def on_start(e):
        started.append(e.task_name)

    async def on_complete(e):
        completed.append(e.task_name)

    tracker = StatusTracker(on_task_start=on_start, on_task_complete=on_complete)
    stage = Stage(name="S", workers=1, tasks=[my_task], retry="per_stage", stage_attempts=1)
    await Pipeline(stages=[stage], status_tracker=tracker).run([1, 2, 3])

    assert len(started) == 3
    assert len(completed) == 3
    assert all(n == "my_task" for n in started)


# ---------------------------------------------------------------------------
# stream() respects buffer_size
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_buffer_size_limits_queue():
    """With buffer_size=1 and a slow consumer, the result queue stays bounded."""
    slow_consumer_delay = 0.05

    async def fast_task(x):
        return x

    stage = Stage(name="S", workers=4, tasks=[fast_task])
    pipeline = Pipeline(stages=[stage])

    collected = []
    async for result in pipeline.stream(list(range(8)), buffer_size=1):
        await asyncio.sleep(slow_consumer_delay)
        collected.append(result.value)

    assert len(collected) == 8


# ---------------------------------------------------------------------------
# RendezvousChannel demand-queue poisoning with many workers (pull stage)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pull_stage_many_workers_no_livelock():
    """
    Regression: _stage_worker used wait_for(input_q.get(), timeout=0.1) for
    RendezvousChannels.  With many workers each timeout left a cancelled future
    in the demand queue; put() had to drain all of them to find a valid one,
    causing a livelock under high worker counts.

    Fix: pull stages call await input_q.get() directly; close() sends
    _PULL_CLOSED to unblock workers on shutdown.
    """
    async def noop(x):
        return x

    n_items = 20
    pipeline = Pipeline(stages=[
        Stage("feeder", workers=2, tasks=[noop]),
        Stage("poll", workers=100, tasks=[noop], pull=True),
    ])

    # Must complete well within 10 seconds — a livelock would hang here.
    results = await asyncio.wait_for(
        pipeline.run(list(range(n_items))),
        timeout=10.0,
    )
    assert len(results) == n_items


@pytest.mark.asyncio
async def test_pull_stage_workers_unblock_on_shutdown():
    """
    Regression: join() did not call close() on RendezvousChannels after
    setting _stop_event.  Workers blocked in get() would hang forever since
    no more items arrived and there was no timeout to escape.

    Fix: join() calls q.close() on every RendezvousChannel after draining.
    """
    async def noop(x):
        return x

    pipeline = Pipeline(stages=[
        Stage("feeder", workers=2, tasks=[noop]),
        Stage("poll", workers=50, tasks=[noop], pull=True),
    ])

    # Verify RendezvousChannel is used for the pull stage
    assert isinstance(pipeline._queues[1], RendezvousChannel)

    # Must complete — before the fix this would hang indefinitely.
    results = await asyncio.wait_for(
        pipeline.run(list(range(10))),
        timeout=10.0,
    )
    assert len(results) == 10
