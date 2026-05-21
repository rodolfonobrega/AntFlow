"""
Batch API Simulation — comparing approaches for the OpenAI polling pattern.

Goal:
- Upload buffer: 5 files pre-uploaded and ready
- Submit: only when a poll worker is free
- N jobs being monitored simultaneously
- Only K poll API calls at once (rate limit)

We test 3 approaches and compare results.
"""

import asyncio
import time

from antflow import Pipeline, Stage
from antflow.context import rate_limit


# ---------------------------------------------------------------------------
# Config (small numbers for fast simulation)
# ---------------------------------------------------------------------------

TOTAL_FILES = 8
UPLOAD_WORKERS = 2
UPLOAD_BUFFER = 5
MAX_JOBS = 8           # max jobs in-flight (workers on poll stage)
POLL_CONCURRENCY = 2   # max simultaneous poll API calls
POLLS_TO_COMPLETE = 3  # each job needs 3 polls to finish
UPLOAD_TIME = 0.05
SUBMIT_TIME = 0.01
POLL_CALL_TIME = 0.01
POLL_SLEEP = 0.02


# ---------------------------------------------------------------------------
# Shared tracking
# ---------------------------------------------------------------------------

def make_tracker():
    return {
        "poll_counts": {},
        "concurrent_polls": 0,
        "max_concurrent_polls": 0,
        "concurrent_jobs": 0,
        "max_concurrent_jobs": 0,
    }


# ---------------------------------------------------------------------------
# APPROACH 1: pull=True + manual asyncio.Semaphore inside loop
# ---------------------------------------------------------------------------

async def approach_1():
    t = make_tracker()
    poll_sem = asyncio.Semaphore(POLL_CONCURRENCY)

    async def upload(fid):
        await asyncio.sleep(UPLOAD_TIME)
        return f"up_{fid}"

    async def submit_and_poll(uploaded_id):
        job_id = f"job_{uploaded_id}"
        await asyncio.sleep(SUBMIT_TIME)
        t["concurrent_jobs"] += 1
        t["max_concurrent_jobs"] = max(t["max_concurrent_jobs"], t["concurrent_jobs"])

        while True:
            async with poll_sem:
                t["concurrent_polls"] += 1
                t["max_concurrent_polls"] = max(t["max_concurrent_polls"], t["concurrent_polls"])
                await asyncio.sleep(POLL_CALL_TIME)
                t["concurrent_polls"] -= 1

            t["poll_counts"][job_id] = t["poll_counts"].get(job_id, 0) + 1
            if t["poll_counts"][job_id] >= POLLS_TO_COMPLETE:
                t["concurrent_jobs"] -= 1
                return f"result_{job_id}"
            await asyncio.sleep(POLL_SLEEP)

    pipeline = Pipeline(stages=[
        Stage("upload", workers=UPLOAD_WORKERS, tasks=[upload], queue_capacity=UPLOAD_BUFFER),
        Stage("submit_and_poll", workers=MAX_JOBS, tasks=[submit_and_poll], pull=True),
    ])

    t0 = time.time()
    results = await pipeline.run([f"f{i}" for i in range(TOTAL_FILES)])
    elapsed = time.time() - t0

    return {
        "name": "pull=True + manual Semaphore",
        "results": len(results),
        "max_concurrent_polls": t["max_concurrent_polls"],
        "max_concurrent_jobs": t["max_concurrent_jobs"],
        "time": elapsed,
    }


# ---------------------------------------------------------------------------
# APPROACH 2: pull=True + task_concurrency_limits (wraps entire function)
# ---------------------------------------------------------------------------

async def approach_2():
    t = make_tracker()

    async def upload(fid):
        await asyncio.sleep(UPLOAD_TIME)
        return f"up_{fid}"

    async def submit_and_poll(uploaded_id):
        job_id = f"job_{uploaded_id}"
        await asyncio.sleep(SUBMIT_TIME)
        t["concurrent_jobs"] += 1
        t["max_concurrent_jobs"] = max(t["max_concurrent_jobs"], t["concurrent_jobs"])

        while True:
            t["concurrent_polls"] += 1
            t["max_concurrent_polls"] = max(t["max_concurrent_polls"], t["concurrent_polls"])
            await asyncio.sleep(POLL_CALL_TIME)
            t["concurrent_polls"] -= 1

            t["poll_counts"][job_id] = t["poll_counts"].get(job_id, 0) + 1
            if t["poll_counts"][job_id] >= POLLS_TO_COMPLETE:
                t["concurrent_jobs"] -= 1
                return f"result_{job_id}"
            await asyncio.sleep(POLL_SLEEP)

    pipeline = Pipeline(stages=[
        Stage("upload", workers=UPLOAD_WORKERS, tasks=[upload], queue_capacity=UPLOAD_BUFFER),
        Stage("submit_and_poll", workers=MAX_JOBS, tasks=[submit_and_poll], pull=True,
              task_concurrency_limits={"submit_and_poll": POLL_CONCURRENCY}),
    ])

    t0 = time.time()
    results = await asyncio.wait_for(
        pipeline.run([f"f{i}" for i in range(TOTAL_FILES)]),
        timeout=10.0,
    )
    elapsed = time.time() - t0

    return {
        "name": "pull=True + task_concurrency_limits",
        "results": len(results),
        "max_concurrent_polls": t["max_concurrent_polls"],
        "max_concurrent_jobs": t["max_concurrent_jobs"],
        "time": elapsed,
    }


# ---------------------------------------------------------------------------
# APPROACH 3: Separate submit + poll stages, pull=True on poll
# ---------------------------------------------------------------------------

async def approach_3():
    t = make_tracker()
    poll_sem = asyncio.Semaphore(POLL_CONCURRENCY)

    async def upload(fid):
        await asyncio.sleep(UPLOAD_TIME)
        return f"up_{fid}"

    async def submit(uploaded_id):
        job_id = f"job_{uploaded_id}"
        await asyncio.sleep(SUBMIT_TIME)
        return job_id

    async def poll_until_done(job_id):
        t["concurrent_jobs"] += 1
        t["max_concurrent_jobs"] = max(t["max_concurrent_jobs"], t["concurrent_jobs"])

        while True:
            async with poll_sem:
                t["concurrent_polls"] += 1
                t["max_concurrent_polls"] = max(t["max_concurrent_polls"], t["concurrent_polls"])
                await asyncio.sleep(POLL_CALL_TIME)
                t["concurrent_polls"] -= 1

            t["poll_counts"][job_id] = t["poll_counts"].get(job_id, 0) + 1
            if t["poll_counts"][job_id] >= POLLS_TO_COMPLETE:
                t["concurrent_jobs"] -= 1
                return f"result_{job_id}"
            await asyncio.sleep(POLL_SLEEP)

    pipeline = Pipeline(stages=[
        Stage("upload", workers=UPLOAD_WORKERS, tasks=[upload], queue_capacity=UPLOAD_BUFFER),
        Stage("submit", workers=2, tasks=[submit]),
        Stage("poll", workers=MAX_JOBS, tasks=[poll_until_done], pull=True),
    ])

    t0 = time.time()
    results = await pipeline.run([f"f{i}" for i in range(TOTAL_FILES)])
    elapsed = time.time() - t0

    return {
        "name": "upload + submit + poll(pull=True) + manual Semaphore",
        "results": len(results),
        "max_concurrent_polls": t["max_concurrent_polls"],
        "max_concurrent_jobs": t["max_concurrent_jobs"],
        "time": elapsed,
    }


# ---------------------------------------------------------------------------
# APPROACH 4: pull=True + call_concurrency (NEW FEATURE — no manual semaphore)
# ---------------------------------------------------------------------------

async def approach_4():
    t = make_tracker()

    async def upload(fid):
        await asyncio.sleep(UPLOAD_TIME)
        return f"up_{fid}"

    async def submit_and_poll(uploaded_id):
        job_id = f"job_{uploaded_id}"
        await asyncio.sleep(SUBMIT_TIME)
        t["concurrent_jobs"] += 1
        t["max_concurrent_jobs"] = max(t["max_concurrent_jobs"], t["concurrent_jobs"])

        while True:
            async with rate_limit():
                t["concurrent_polls"] += 1
                t["max_concurrent_polls"] = max(t["max_concurrent_polls"], t["concurrent_polls"])
                await asyncio.sleep(POLL_CALL_TIME)
                t["concurrent_polls"] -= 1

            t["poll_counts"][job_id] = t["poll_counts"].get(job_id, 0) + 1
            if t["poll_counts"][job_id] >= POLLS_TO_COMPLETE:
                t["concurrent_jobs"] -= 1
                return f"result_{job_id}"
            await asyncio.sleep(POLL_SLEEP)

    pipeline = Pipeline(stages=[
        Stage("upload", workers=UPLOAD_WORKERS, tasks=[upload], queue_capacity=UPLOAD_BUFFER),
        Stage("submit_and_poll", workers=MAX_JOBS, tasks=[submit_and_poll], pull=True,
              call_concurrency=POLL_CONCURRENCY),
    ])

    t0 = time.time()
    results = await pipeline.run([f"f{i}" for i in range(TOTAL_FILES)])
    elapsed = time.time() - t0

    return {
        "name": "pull=True + call_concurrency (NEW)",
        "results": len(results),
        "max_concurrent_polls": t["max_concurrent_polls"],
        "max_concurrent_jobs": t["max_concurrent_jobs"],
        "time": elapsed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("BATCH API SIMULATION")
    print(f"  {TOTAL_FILES} files | {MAX_JOBS} max jobs | {POLL_CONCURRENCY} concurrent polls")
    print(f"  Each job needs {POLLS_TO_COMPLETE} polls to complete")
    print("=" * 70)

    all_results = []

    # Approach 1
    print("\n[1] Running: pull=True + manual Semaphore ...")
    r1 = await approach_1()
    all_results.append(r1)
    print(f"    OK: {r1['results']} results, {r1['time']:.2f}s")
    print(f"    max_polls={r1['max_concurrent_polls']}, max_jobs={r1['max_concurrent_jobs']}")

    # Approach 2
    print("\n[2] Running: pull=True + task_concurrency_limits ...")
    try:
        r2 = await approach_2()
        all_results.append(r2)
        print(f"    OK: {r2['results']} results, {r2['time']:.2f}s")
        print(f"    max_polls={r2['max_concurrent_polls']}, max_jobs={r2['max_concurrent_jobs']}")
    except asyncio.TimeoutError:
        print("    TIMEOUT (deadlock or too slow)")
        all_results.append({"name": "pull=True + task_concurrency_limits", "results": 0,
                           "max_concurrent_polls": "?", "max_concurrent_jobs": "?", "time": ">10s"})

    # Approach 3
    print("\n[3] Running: upload + submit + poll(pull=True) + manual Semaphore ...")
    r3 = await approach_3()
    all_results.append(r3)
    print(f"    OK: {r3['results']} results, {r3['time']:.2f}s")
    print(f"    max_polls={r3['max_concurrent_polls']}, max_jobs={r3['max_concurrent_jobs']}")

    # Approach 4
    print("\n[4] Running: pull=True + call_concurrency (NEW FEATURE) ...")
    r4 = await approach_4()
    all_results.append(r4)
    print(f"    OK: {r4['results']} results, {r4['time']:.2f}s")
    print(f"    max_polls={r4['max_concurrent_polls']}, max_jobs={r4['max_concurrent_jobs']}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Approach':<50} {'Polls':<8} {'Jobs':<8} {'Time':<8} {'OK?'}")
    print("-" * 70)
    for r in all_results:
        polls_ok = r['max_concurrent_polls'] <= POLL_CONCURRENCY if isinstance(r['max_concurrent_polls'], int) else "?"
        jobs_ok = r['max_concurrent_jobs'] > POLL_CONCURRENCY if isinstance(r['max_concurrent_jobs'], int) else "?"
        ok = "YES" if polls_ok and jobs_ok else "NO"
        t_str = str(r['time']) if isinstance(r['time'], str) else f"{r['time']:.2f}s"
        print(f"  {r['name']:<48} {str(r['max_concurrent_polls']):<8} {str(r['max_concurrent_jobs']):<8} {t_str:<8} {ok}")

    print(f"\nExpected: max_polls <= {POLL_CONCURRENCY}, max_jobs > {POLL_CONCURRENCY} (ideally up to {MAX_JOBS})")


if __name__ == "__main__":
    asyncio.run(main())
