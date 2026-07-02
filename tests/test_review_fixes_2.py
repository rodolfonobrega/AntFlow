"""Regression tests for the second round of concurrency/robustness fixes.

Each test maps to a numbered finding from the review:
  #1 run() leaking workers on cancellation
  #2 executor worker dying on BaseException (e.g. CancelledError)
  #3 StatusTracker callback failure aborting the whole pipeline
  #4 shutdown() dropping in-flight per_stage retry items
  #5 submit(retries=N) leaking tenacity.RetryError
  #6 executor shutdown(wait=False) blocking anyway
  #7 as_completed(timeout=...) resetting the deadline every iteration
  #8 on_task_fail firing on transient per_stage retries
  #12 duplicate stage names
"""

import asyncio
import time

import pytest

from antflow import AsyncExecutor, Pipeline, Stage, StatusTracker
from antflow.exceptions import StageValidationError


# --------------------------------------------------------------------------- #
# #1 — cancelling run() must shut down all workers, not leak them
# --------------------------------------------------------------------------- #
async def test_run_cancellation_shuts_down_workers():
    async def slow(x):
        await asyncio.sleep(10)
        return x

    pipeline = Pipeline(stages=[Stage("slow", workers=2, tasks=[slow])])

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(pipeline.run(list(range(5))), timeout=0.2)

    await asyncio.sleep(0.05)
    assert pipeline._shutdown is True
    assert all(t.done() for t in pipeline._worker_tasks)


# --------------------------------------------------------------------------- #
# #2 — a task raising CancelledError must not permanently kill its worker
# --------------------------------------------------------------------------- #
async def test_worker_survives_task_cancelled_error():
    async def cancels():
        raise asyncio.CancelledError("boom")

    async def ok(x):
        return x * 2

    async with AsyncExecutor(max_workers=2) as executor:
        bad_future = executor.submit(cancels)
        good_future = executor.submit(ok, 21)

        with pytest.raises(asyncio.CancelledError):
            await bad_future.result()

        assert await good_future.result() == 42


# --------------------------------------------------------------------------- #
# #3 — a raising on_status_change callback must not abort the pipeline
# --------------------------------------------------------------------------- #
async def test_tracker_callback_error_does_not_abort_pipeline():
    async def on_status_change(event):
        raise RuntimeError("callback exploded")

    tracker = StatusTracker(on_status_change=on_status_change)

    async def task(x):
        return x * 2

    pipeline = Pipeline(stages=[Stage("stage", workers=2, tasks=[task])], status_tracker=tracker)
    results = await pipeline.run([1, 2, 3])

    assert sorted(r.value for r in results) == [2, 4, 6]


# --------------------------------------------------------------------------- #
# #4 — shutdown() must drain the retry queues too, not just the input queues
# --------------------------------------------------------------------------- #
async def test_shutdown_drains_retry_queues():
    async def always_fails(x):
        raise ValueError("always fails")

    stage = Stage(
        "stage", workers=1, tasks=[always_fails], retry="per_stage", stage_attempts=3,
    )
    pipeline = Pipeline(stages=[stage])
    await pipeline.start()
    await pipeline.feed([1])

    await asyncio.sleep(0.05)  # let it fail once and land in the retry queue
    await pipeline.shutdown()

    assert all(rq.empty() for rq in pipeline._retry_queues.values())


# --------------------------------------------------------------------------- #
# #5 — submit(retries=N) must surface the original exception, not RetryError
# --------------------------------------------------------------------------- #
async def test_submit_retries_reraises_original_exception():
    async def always_fails():
        raise ValueError("nope")

    async with AsyncExecutor(max_workers=1) as executor:
        future = executor.submit(always_fails, retries=2, retry_delay=0.01)
        with pytest.raises(ValueError, match="nope"):
            await future.result()


# --------------------------------------------------------------------------- #
# #6 — shutdown(wait=False) must return promptly
# --------------------------------------------------------------------------- #
async def test_shutdown_wait_false_does_not_block():
    async def slow(x):
        await asyncio.sleep(0.3)
        return x

    executor = AsyncExecutor(max_workers=5)
    futures = [executor.submit(slow, i) for i in range(5)]

    start = time.monotonic()
    await executor.shutdown(wait=False)
    elapsed = time.monotonic() - start

    assert elapsed < 0.2
    await asyncio.gather(*[f.result() for f in futures], return_exceptions=True)


# --------------------------------------------------------------------------- #
# #7 — as_completed(timeout=...) must use a cumulative deadline
# --------------------------------------------------------------------------- #
async def test_as_completed_timeout_is_cumulative():
    async def slow(delay):
        await asyncio.sleep(delay)
        return delay

    async with AsyncExecutor(max_workers=4) as executor:
        # Staggered completions: 0.35s apart, each individually under the
        # 0.4s timeout — only a per-iteration (non-cumulative) timeout would
        # let this run to completion.
        futures = [executor.submit(slow, 0.35 * (i + 1)) for i in range(4)]

        start = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            async for _ in executor.as_completed(futures, timeout=0.4):
                pass
        elapsed = time.monotonic() - start

        assert elapsed < 0.6


# --------------------------------------------------------------------------- #
# #8 — on_task_fail must not fire for a per_stage failure that will retry
# --------------------------------------------------------------------------- #
async def test_on_task_fail_not_fired_on_transient_per_stage_retry():
    attempts = {"count": 0}
    fail_events = []
    retry_events = []

    async def flaky(x):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ValueError("transient")
        return x

    stage = Stage(
        "stage", workers=1, tasks=[flaky], retry="per_stage", stage_attempts=3,
    )
    async def on_fail(e):
        fail_events.append(e)

    async def on_retry(e):
        retry_events.append(e)

    tracker = StatusTracker(on_task_fail=on_fail, on_task_retry=on_retry)
    pipeline = Pipeline(stages=[stage], status_tracker=tracker)
    results = await pipeline.run([1])

    assert results[0].value == 1
    assert len(fail_events) == 0
    assert len(retry_events) == 1


# --------------------------------------------------------------------------- #
# #12 — duplicate stage names must be rejected at construction time
# --------------------------------------------------------------------------- #
async def test_duplicate_stage_names_rejected():
    async def task(x):
        return x

    with pytest.raises(StageValidationError, match="Duplicate stage name"):
        Pipeline(stages=[
            Stage("fetch", workers=1, tasks=[task]),
            Stage("transform", workers=1, tasks=[task]),
            Stage("fetch", workers=1, tasks=[task]),
        ])
