"""
OpenAI Batch Pipeline using pull=True for demand-driven job submission.

Problem
-------
A normal push pipeline submits batch jobs as fast as possible and queues them
for the polling stage.  Jobs sitting in that queue are *already running on
OpenAI* — they just have no observer yet.  A job can finish while waiting in
the queue, so the slot it occupies on OpenAI is wasted until a polling worker
finally picks it up.

Solution — pull=True on the poll stage
---------------------------------------
With pull=True the poll stage workers signal readiness *before* a job is
submitted.  Upstream (submit) only produces when downstream (poll) has a free
worker.  This means:

  * A job is submitted exactly when a poll worker is ready to watch it.
  * No job ever sits unobserved in a buffer.
  * ``workers=N`` on the pull stage is a hard cap on jobs in-flight.

Pipeline shape
--------------
  upload (push, 2 workers)
    → submit_and_poll (pull=True, 5 workers)   ← key stage
      → download (push, 3 workers)

The submit_and_poll task submits the job *and* polls it to completion in one
call.  The pull stage ensures that task only starts when a worker is free,
so at most 5 jobs are ever running on OpenAI at once.

Customising / testing
---------------------
Pass async callables to override the simulated OpenAI operations::

    pipeline = BatchPipeline(
        poll_fn=my_mock_poll,
        download_fn=my_mock_download,
    )
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from antflow import Pipeline, Stage


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

UploadFn   = Callable[[str], Awaitable[str]]
SubmitFn   = Callable[[str], Awaitable[str]]
PollFn     = Callable[[str], Awaitable[tuple[str, Any]]]
DownloadFn = Callable[[Any], Awaitable[Any]]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FileTask:
    file_id: str
    data: Any


@dataclass
class BatchResult:
    file_id: str
    result_ref: Any


# ---------------------------------------------------------------------------
# Simulated OpenAI calls  (replace with real SDK calls)
# ---------------------------------------------------------------------------


async def _sim_upload(file_id: str) -> str:
    await asyncio.sleep(random.uniform(0.3, 0.8))
    return f"oai_file_{file_id}"


async def _sim_submit(openai_file_id: str) -> str:
    await asyncio.sleep(0.05)
    return f"batch_{openai_file_id}"


async def _sim_poll(batch_id: str) -> tuple[str, Any]:
    await asyncio.sleep(random.uniform(0.1, 0.4))
    done = random.random() < 0.4
    return ("complete", f"ref_{batch_id}") if done else ("in_progress", None)


async def _sim_download(result_ref: Any) -> Any:
    await asyncio.sleep(0.05)
    return f"result_{result_ref}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class BatchPipeline:
    """
    Batch pipeline with pull=True on the submit+poll stage.

    Args:
        upload_workers:  concurrent upload workers (default 2).
        poll_workers:    concurrent poll workers = hard cap on jobs in-flight
                         on OpenAI at any time (default 5).
        download_workers: concurrent download workers (default 3).
        poll_interval:   seconds between poll attempts (default 0.5).
        upload_fn:       replaces the simulated upload call.
        submit_fn:       replaces the simulated submit call.
        poll_fn:         replaces the simulated poll call.
        download_fn:     replaces the simulated download call.
    """

    def __init__(
        self,
        *,
        upload_workers: int = 2,
        poll_workers: int = 5,
        download_workers: int = 3,
        poll_interval: float = 0.5,
        upload_fn:   UploadFn   | None = None,
        submit_fn:   SubmitFn   | None = None,
        poll_fn:     PollFn     | None = None,
        download_fn: DownloadFn | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._upload_fn   = upload_fn   or _sim_upload
        self._submit_fn   = submit_fn   or _sim_submit
        self._poll_fn     = poll_fn     or _sim_poll
        self._download_fn = download_fn or _sim_download

        self._pipeline = Pipeline(stages=[
            Stage(
                name="upload",
                workers=upload_workers,
                tasks=[self._upload],
            ),
            # pull=True: this worker only receives an uploaded file when it is
            # free to submit AND poll the resulting job immediately.
            # At most `poll_workers` jobs are ever in-flight on OpenAI.
            Stage(
                name="submit_and_poll",
                workers=poll_workers,
                tasks=[self._submit_and_poll],
                pull=True,
            ),
            Stage(
                name="download",
                workers=download_workers,
                tasks=[self._download],
            ),
        ])

    # ------------------------------------------------------------------
    # Stage tasks
    # ------------------------------------------------------------------

    async def _upload(self, task: FileTask) -> dict:
        openai_file_id = await self._upload_fn(task.file_id)
        print(f"[upload]  {task.file_id} -> {openai_file_id}")
        return {"file_id": task.file_id, "openai_file_id": openai_file_id}

    async def _submit_and_poll(self, uploaded: dict) -> BatchResult:
        """Submit the batch job and poll until it completes.

        Because this stage uses pull=True, this function is only called
        when a worker is available — so no job is ever submitted without
        an observer.
        """
        file_id = uploaded["file_id"]
        openai_file_id = uploaded["openai_file_id"]

        batch_id = await self._submit_fn(openai_file_id)
        print(f"[submit]  {file_id} -> {batch_id}")

        # Poll until done.  The worker is dedicated to this single job,
        # so completions are noticed immediately.
        attempts = 0
        while True:
            attempts += 1
            status, result_ref = await self._poll_fn(batch_id)
            if status == "complete":
                print(f"[poll]    {batch_id} done after {attempts} poll(s)")
                return BatchResult(file_id=file_id, result_ref=result_ref)
            await asyncio.sleep(self._poll_interval)

    async def _download(self, job: BatchResult) -> Any:
        result = await self._download_fn(job.result_ref)
        print(f"[download] {job.file_id} -> {result}")
        return result

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self, files: list[FileTask]) -> list[Any]:
        results = await self._pipeline.run(files)
        return [r.value for r in results]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


async def main() -> None:
    files = [FileTask(file_id=f"file_{i:03d}", data=f"payload_{i}") for i in range(12)]

    pipeline = BatchPipeline(
        upload_workers=2,
        poll_workers=5,       # hard cap: at most 5 jobs on OpenAI at once
        download_workers=3,
        poll_interval=0.2,
    )

    results = await pipeline.run(files)
    print(f"\nDone — {len(results)} results collected")


if __name__ == "__main__":
    asyncio.run(main())
