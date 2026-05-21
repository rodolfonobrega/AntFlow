"""Tests for examples/openai_batch_prefetch.py.

Each test injects fast, deterministic callables in place of the real OpenAI
calls so the suite is self-contained and runs in under a second.
"""

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import the example module without requiring an __init__.py in examples/
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "openai_batch_prefetch",
    Path(__file__).parent.parent / "examples" / "openai_batch_prefetch.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

OpenAIBatchPipeline = _mod.OpenAIBatchPipeline
FileTask = _mod.FileTask


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_files(n: int) -> list:
    return [FileTask(file_id=f"f{i}", data=None) for i in range(n)]


def instant_upload(file_id: str):
    async def _fn(fid: str) -> str:
        return f"up_{fid}"
    return _fn(file_id)


async def _instant_upload(file_id: str) -> str:
    return f"up_{file_id}"


async def _instant_submit(openai_file_id: str) -> str:
    return f"batch_{openai_file_id}"


async def _always_complete_poll(batch_id: str) -> tuple[str, Any]:
    return ("complete", f"ref_{batch_id}")


async def _instant_download(result_ref: Any) -> Any:
    return f"result_{result_ref}"


def _fast_pipeline(**kwargs) -> OpenAIBatchPipeline:
    """Pipeline wired with instant no-op callables and tight timing."""
    defaults = dict(
        upload_workers=2,
        upload_prefetch=10,
        max_in_flight=50,
        poll_parallelism=5,
        poll_interval=0.01,
        upload_fn=_instant_upload,
        submit_fn=_instant_submit,
        poll_fn=_always_complete_poll,
        download_fn=_instant_download,
    )
    defaults.update(kwargs)
    return OpenAIBatchPipeline(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_results_returned():
    """Every input file produces exactly one result."""
    results = await _fast_pipeline().run(make_files(8))
    assert len(results) == 8


@pytest.mark.asyncio
async def test_empty_input():
    """Empty input completes immediately with no results."""
    results = await _fast_pipeline().run([])
    assert results == []


@pytest.mark.asyncio
async def test_single_file():
    results = await _fast_pipeline().run(make_files(1))
    assert len(results) == 1


@pytest.mark.asyncio
async def test_upload_concurrency_limit():
    """Concurrent uploads must never exceed upload_workers."""
    active = 0
    max_active = 0

    async def tracked_upload(file_id: str) -> str:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return f"up_{file_id}"

    await _fast_pipeline(upload_workers=2, upload_fn=tracked_upload).run(make_files(10))

    assert max_active <= 2
    assert max_active == 2


@pytest.mark.asyncio
async def test_in_flight_cap_respected():
    """At most max_in_flight jobs may be submitted-but-not-yet-complete."""
    active = 0
    max_active = 0
    # Track: increment on submit, decrement when poll returns complete.
    call_count: dict[str, int] = {}

    async def tracking_submit(openai_file_id: str) -> str:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        return f"batch_{openai_file_id}"

    async def two_round_poll(batch_id: str) -> tuple[str, Any]:
        nonlocal active
        n = call_count.get(batch_id, 0) + 1
        call_count[batch_id] = n
        if n >= 2:
            active -= 1
            return ("complete", f"ref_{batch_id}")
        return ("in_progress", None)

    cap = 3
    await _fast_pipeline(
        max_in_flight=cap,
        upload_workers=1,
        upload_prefetch=10,
        submit_fn=tracking_submit,
        poll_fn=two_round_poll,
        poll_interval=0.01,
    ).run(make_files(9))

    assert max_active <= cap
    assert max_active == cap


@pytest.mark.asyncio
async def test_poll_parallelism_respected():
    """Concurrent polls within a single sweeper round must not exceed poll_parallelism."""
    concurrent = 0
    max_concurrent = 0

    async def tracked_poll(batch_id: str) -> tuple[str, Any]:
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        await asyncio.sleep(0.02)
        concurrent -= 1
        return ("complete", f"ref_{batch_id}")

    parallelism = 3
    # Use max_in_flight >= total so all jobs land in-flight at once,
    # maximising the chance of a full-parallelism sweeper round.
    await _fast_pipeline(
        poll_parallelism=parallelism,
        max_in_flight=10,
        poll_fn=tracked_poll,
        poll_interval=0.0,
    ).run(make_files(10))

    assert max_concurrent <= parallelism
    assert max_concurrent == parallelism


@pytest.mark.asyncio
async def test_slot_released_before_download_completes():
    """
    The in-flight slot must be freed as soon as the sweeper confirms
    completion, not after the download finishes.

    With max_in_flight=1 and a slow download, the second job must be
    submitted *before* the first download completes.
    """
    submit_times: list[float] = []
    download_end_times: list[float] = []

    async def tracking_submit(openai_file_id: str) -> str:
        submit_times.append(asyncio.get_event_loop().time())
        return f"batch_{openai_file_id}"

    async def slow_download(result_ref: Any) -> Any:
        await asyncio.sleep(0.05)
        download_end_times.append(asyncio.get_event_loop().time())
        return f"result_{result_ref}"

    await _fast_pipeline(
        max_in_flight=1,
        upload_workers=1,
        upload_prefetch=2,
        submit_fn=tracking_submit,
        poll_fn=_always_complete_poll,
        download_fn=slow_download,
        poll_interval=0.01,
    ).run(make_files(2))

    assert len(submit_times) == 2
    assert len(download_end_times) == 2
    # Second submit must happen before the first download finishes.
    assert submit_times[1] < min(download_end_times)
