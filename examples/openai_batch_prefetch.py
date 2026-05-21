"""
OpenAI Batch Pipeline — two implementations for comparison.

This module contains two classes that solve the same problem differently:

OpenAIBatchPipeline  — sweeper-based (lower worker count, bulk-poll friendly)
PullBatchPipeline    — pull=True based (simpler code, same correctness guarantees)

Both guarantee that no submitted job is ever left unmonitored.

--------------------------------------------------------------------
OpenAIBatchPipeline (sweeper)
--------------------------------------------------------------------
Constraints
- Upload:   max N concurrent workers; keeps up to ``upload_prefetch`` files
            pre-uploaded in a bounded buffer so the submit stage never idles.
- Submit:   at most ``max_in_flight`` batch jobs outstanding at any time.
            The semaphore is acquired before submit and released the moment
            the sweeper confirms completion — not after download.
- Polling:  a background sweeper watches **all** in-flight jobs every round,
            running at most ``poll_parallelism`` polls concurrently.
- Download: triggered immediately after the sweeper releases a slot, so slow
            downloads never block new submissions.

Why a sweeper instead of a poll queue
A normal queue holds slots until a worker picks them up, so a completed job
keeps its in-flight slot until it reaches the front of the queue.  The sweeper
solves this by scanning *all* in-flight jobs every round: as soon as a job
finishes, its slot is released immediately regardless of position.

When to prefer the sweeper:
- The API supports bulk polling (one call to check N jobs at once) — the
  sweeper can gather all in-flight IDs and send a single batched request.
- You want fewer OS-level tasks: one sweeper loop serves all in-flight jobs,
  vs. one asyncio task per job with pull=True.

--------------------------------------------------------------------
PullBatchPipeline (pull=True)
--------------------------------------------------------------------
Uses pull=True on the submit+poll stage so a job is only submitted when a
worker is free to monitor it immediately.  A shared semaphore caps concurrent
poll API calls the same way the sweeper does.

When to prefer pull=True:
- Simpler code — no sweeper task, no extra semaphore/lock/download queue.
- Each worker owns exactly one job from submit to completion; no shared state.
- Bulk polling is not needed or not supported by the API.

--------------------------------------------------------------------
Customising / testing (both classes)
--------------------------------------------------------------------
Pass async callables to ``upload_fn``, ``submit_fn``, ``poll_fn`` and
``download_fn`` to replace the default simulated OpenAI calls::

    pipeline = OpenAIBatchPipeline(poll_fn=my_mock_poll)
    pipeline = PullBatchPipeline(poll_fn=my_mock_poll)
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from antflow import Pipeline, Stage


# ---------------------------------------------------------------------------
# Type aliases for injectable callables
# ---------------------------------------------------------------------------

UploadFn = Callable[[str], Awaitable[str]]
SubmitFn = Callable[[str], Awaitable[str]]
PollFn = Callable[[str], Awaitable[tuple[str, Any]]]
DownloadFn = Callable[[Any], Awaitable[Any]]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FileTask:
    file_id: str
    data: Any


@dataclass
class UploadedFile:
    file_id: str
    openai_file_id: str


@dataclass
class BatchJob:
    job_id: str
    openai_batch_id: str
    file: UploadedFile


# ---------------------------------------------------------------------------
# Simulated OpenAI calls  (replace with real SDK calls)
# ---------------------------------------------------------------------------


async def openai_upload(file_id: str) -> str:
    await asyncio.sleep(random.uniform(0.5, 1.5))
    return f"oai_file_{file_id}"


async def openai_submit_batch(openai_file_id: str) -> str:
    await asyncio.sleep(0.1)
    return f"batch_{openai_file_id}"


async def openai_poll_batch(batch_id: str) -> tuple[str, Any]:
    await asyncio.sleep(random.uniform(0.05, 0.2))
    done = random.random() < 0.3
    return ("complete", f"result_ref_{batch_id}") if done else ("in_progress", None)


async def openai_download(result_ref: Any) -> Any:
    await asyncio.sleep(0.1)
    return f"downloaded_{result_ref}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class OpenAIBatchPipeline:
    def __init__(
        self,
        *,
        upload_workers: int = 2,
        upload_prefetch: int = 10,
        max_in_flight: int = 50,
        poll_parallelism: int = 5,
        poll_interval: float = 1.0,
        upload_fn: UploadFn | None = None,
        submit_fn: SubmitFn | None = None,
        poll_fn: PollFn | None = None,
        download_fn: DownloadFn | None = None,
    ):
        self._upload_workers = upload_workers
        self._poll_parallelism = poll_parallelism
        self._poll_interval = poll_interval

        self._upload_fn = upload_fn or openai_upload
        self._submit_fn = submit_fn or openai_submit_batch
        self._poll_fn = poll_fn or openai_poll_batch
        self._download_fn = download_fn or openai_download

        # Uploaded files ready to be submitted; bounded so upload workers
        # naturally pause when the consumer (submit) is stuck behind the
        # in-flight cap.
        self._upload_buffer: asyncio.Queue[UploadedFile] = asyncio.Queue(
            maxsize=upload_prefetch
        )

        # Global cap: acquired on submit, released when sweeper confirms done.
        self._in_flight_sem = asyncio.Semaphore(max_in_flight)

        # Live map of all submitted-but-not-yet-complete jobs.
        self._in_flight: dict[str, BatchJob] = {}
        self._in_flight_lock = asyncio.Lock()

        # Bounds concurrent polls inside each sweeper round.
        self._poll_sem = asyncio.Semaphore(poll_parallelism)

        # Completed jobs waiting for download.
        self._download_queue: asyncio.Queue[tuple[BatchJob, Any]] = asyncio.Queue()

        self._results: list[Any] = []

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    async def _upload_worker(self, worker_id: int, file_queue: asyncio.Queue) -> None:
        while True:
            task: FileTask | None = await file_queue.get()
            if task is None:
                file_queue.task_done()
                return
            print(f"[upload-{worker_id}] uploading {task.file_id}")
            openai_id = await self._upload_fn(task.file_id)
            uploaded = UploadedFile(file_id=task.file_id, openai_file_id=openai_id)
            # Blocks here when the buffer is already full (prefetch satisfied).
            await self._upload_buffer.put(uploaded)
            print(f"[upload-{worker_id}] buffered {task.file_id} -> {openai_id}")
            file_queue.task_done()

    async def _submit_worker(self, total: int) -> None:
        for _ in range(total):
            uploaded = await self._upload_buffer.get()
            # Wait for a free in-flight slot before submitting.
            await self._in_flight_sem.acquire()
            batch_id = await self._submit_fn(uploaded.openai_file_id)
            job = BatchJob(
                job_id=f"job_{uploaded.file_id}",
                openai_batch_id=batch_id,
                file=uploaded,
            )
            async with self._in_flight_lock:
                self._in_flight[job.job_id] = job
                in_flight_count = len(self._in_flight)
            print(f"[submit] {uploaded.file_id} ->{batch_id}  ({in_flight_count} in-flight)")

    async def _sweeper(self) -> None:
        """
        Each round: snapshot all in-flight jobs, poll them all with bounded
        parallelism, release slots for completed ones immediately.
        """
        while True:
            async with self._in_flight_lock:
                snapshot = list(self._in_flight.values())

            if snapshot:
                await asyncio.gather(*[self._poll_one(job) for job in snapshot])

            await asyncio.sleep(self._poll_interval)

    async def _poll_one(self, job: BatchJob) -> None:
        async with self._poll_sem:
            status, result_ref = await self._poll_fn(job.openai_batch_id)

        if status != "complete":
            return

        async with self._in_flight_lock:
            self._in_flight.pop(job.job_id, None)
            remaining = len(self._in_flight)

        # Release the global slot *before* enqueueing download so submit can
        # proceed as soon as possible.
        self._in_flight_sem.release()
        await self._download_queue.put((job, result_ref))
        print(f"[sweeper] {job.job_id} done — slot released ({remaining} in-flight)")

    async def _download_worker(self, total: int) -> None:
        for _ in range(total):
            job, result_ref = await self._download_queue.get()
            result = await self._download_fn(result_ref)
            self._results.append(result)
            print(f"[download] {job.job_id} ->{result}")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self, files: list[FileTask]) -> list[Any]:
        self._results = []
        total = len(files)

        file_queue: asyncio.Queue[FileTask | None] = asyncio.Queue()
        for f in files:
            await file_queue.put(f)

        async def _poison_pills():
            await file_queue.join()
            for _ in range(self._upload_workers):
                await file_queue.put(None)

        upload_tasks = [
            asyncio.create_task(self._upload_worker(i, file_queue))
            for i in range(self._upload_workers)
        ]
        sweeper_task = asyncio.create_task(self._sweeper())

        await asyncio.gather(
            _poison_pills(),
            *upload_tasks,
            self._submit_worker(total),
            self._download_worker(total),
        )

        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass

        return self._results


# ---------------------------------------------------------------------------
# PullBatchPipeline — same guarantees, simpler implementation
# ---------------------------------------------------------------------------


class PullBatchPipeline:
    """
    Upload-prefetch + pull=True pipeline.

    A job is only submitted when a worker is free to monitor it immediately,
    so no job is ever left unobserved.  A shared semaphore limits concurrent
    poll API calls the same way the sweeper does in OpenAIBatchPipeline.

    Args:
        upload_workers:   concurrent upload workers (default 2).
        upload_prefetch:  pre-uploaded files kept ready in the buffer (default 10).
        max_in_flight:    hard cap on jobs submitted to OpenAI at once (default 50).
        poll_parallelism: max concurrent poll API calls across all workers (default 5).
        poll_interval:    seconds between poll attempts per worker (default 1.0).
        upload_fn / submit_fn / poll_fn / download_fn: injectable callables for testing.
    """

    def __init__(
        self,
        *,
        upload_workers: int = 2,
        upload_prefetch: int = 10,
        max_in_flight: int = 50,
        poll_parallelism: int = 5,
        poll_interval: float = 1.0,
        upload_fn: UploadFn | None = None,
        submit_fn: SubmitFn | None = None,
        poll_fn: PollFn | None = None,
        download_fn: DownloadFn | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._upload_fn = upload_fn or openai_upload
        self._submit_fn = submit_fn or openai_submit_batch
        self._poll_fn = poll_fn or openai_poll_batch
        self._download_fn = download_fn or openai_download

        # Caps concurrent poll API calls shared across all workers.
        self._poll_sem = asyncio.Semaphore(poll_parallelism)

        self._pipeline = Pipeline(stages=[
            Stage(
                name="upload",
                workers=upload_workers,
                tasks=[self._upload],
                queue_capacity=upload_prefetch,  # pre-upload buffer
            ),
            # pull=True: a file is only handed to this worker when it is free.
            # The worker submits and polls until done — no job sits unmonitored.
            # max_in_flight workers == hard cap on jobs in-flight on OpenAI.
            Stage(
                name="submit_and_poll",
                workers=max_in_flight,
                tasks=[self._submit_and_poll],
                pull=True,
            ),
            Stage(
                name="download",
                workers=upload_workers,
                tasks=[self._download],
            ),
        ])

    async def _upload(self, task: FileTask) -> UploadedFile:
        openai_id = await self._upload_fn(task.file_id)
        uploaded = UploadedFile(file_id=task.file_id, openai_file_id=openai_id)
        print(f"[upload]  {task.file_id} -> {openai_id}")
        return uploaded

    async def _submit_and_poll(self, uploaded: UploadedFile) -> tuple[BatchJob, Any]:
        batch_id = await self._submit_fn(uploaded.openai_file_id)
        job = BatchJob(
            job_id=f"job_{uploaded.file_id}",
            openai_batch_id=batch_id,
            file=uploaded,
        )
        print(f"[submit]  {uploaded.file_id} -> {batch_id}")

        attempts = 0
        while True:
            attempts += 1
            async with self._poll_sem:
                status, result_ref = await self._poll_fn(job.openai_batch_id)
            if status == "complete":
                print(f"[poll]    {job.job_id} done after {attempts} attempt(s)")
                return job, result_ref
            await asyncio.sleep(self._poll_interval)

    async def _download(self, payload: tuple[BatchJob, Any]) -> Any:
        job, result_ref = payload
        result = await self._download_fn(result_ref)
        print(f"[download] {job.job_id} -> {result}")
        return result

    async def run(self, files: list[FileTask]) -> list[Any]:
        results = await self._pipeline.run(files)
        return [r.value for r in results]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


async def main() -> None:
    files = [FileTask(file_id=f"file_{i:03d}", data=f"payload_{i}") for i in range(20)]

    print("=== OpenAIBatchPipeline (sweeper) ===")
    sweeper_pipeline = OpenAIBatchPipeline(
        upload_workers=2,
        upload_prefetch=10,
        max_in_flight=50,
        poll_parallelism=5,
        poll_interval=0.5,
    )
    results = await sweeper_pipeline.run(files)
    print(f"Finished — {len(results)} results\n")

    print("=== PullBatchPipeline (pull=True) ===")
    pull_pipeline = PullBatchPipeline(
        upload_workers=2,
        upload_prefetch=10,
        max_in_flight=50,
        poll_parallelism=5,
        poll_interval=0.5,
    )
    results = await pull_pipeline.run(files)
    print(f"Finished — {len(results)} results")


if __name__ == "__main__":
    asyncio.run(main())
