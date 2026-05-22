# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.2] - 2026-05-22

### Fixed

*   **RendezvousChannel demand-queue poisoning (`pull=True` stages):** `_stage_worker` was using `wait_for(input_q.get(), timeout=0.1)` for pull stages. Every timeout left a cancelled future in the demand queue; `put()` had to drain all of them to find a valid one, causing a livelock under high worker counts (e.g. 500 workers × 10 timeouts/s = 5 000 cancelled futures/s). Fix: pull stages now call `await input_q.get()` directly — no timeout, no cancelled futures.
*   **Pull-stage workers hang on shutdown:** `join()` set `_stop_event` but did not close `RendezvousChannel`s. Workers blocked in `get()` would hang indefinitely after all items were processed, because no new items arrived and there was no timeout to escape. Fix: `join()` now calls `q.close()` on every `RendezvousChannel` after draining, which sends `_PULL_CLOSED` to all waiting workers so they exit cleanly.

## [0.8.1] - 2026-05-22

### Added

*   **`call_rate` / `call_rate_period` (leaky bucket rate limiting):** New `Stage` parameters that throttle throughput to N calls per time period using `aiolimiter`'s leaky bucket algorithm. Set `call_rate=N` and wrap calls with `async with rate_limit():`. An initial burst of N is allowed; subsequent calls are spaced at `call_rate_period / call_rate` seconds each.
*   **`call_rate_has_capacity(amount=1) -> bool`:** Non-blocking check of remaining rate-limit budget. Useful for adaptive fallback logic.
*   **New tests:** `test_rate_limit.py` (9 tests covering `concurrency_limit`, `rate_limit`, post-burst spacing, combined usage), `test_dashboard_snapshot.py` (7 tests for worker count, in-flight tracking, string IDs, progress monotonicity).

### Changed

*   **`rate_limit()` renamed to `concurrency_limit()`** — the old semaphore-based context manager is now `concurrency_limit()` to accurately describe what it does. The name `rate_limit()` is now used for the true leaky-bucket rate limiter.
*   **`docs/user-guide/concurrency.md` rewritten** — clearer structure with a quick reference table at the top, dedicated `pull=True` section with visual diagrams, sharper `task_concurrency_limits` vs `call_concurrency` distinction, and examples in every section.
*   **`docs/user-guide/pipeline.md`** — Stage config table updated with `call_rate` and `call_rate_period` rows; fixed `queue_capacity` comment to accurately describe items waiting for upload (not pre-uploaded files).
*   **0 ruff lint errors** — all pre-existing E/F/I/N/W violations resolved.

## [0.8.0] - 2026-05-21

### Added

*   **Pull Stages (`pull=True`):** New demand-driven mode for `Stage`. When `pull=True`, downstream workers signal readiness before an item is delivered — there is no buffer between stages. Items are handed off directly via `RendezvousChannel`, a zero-buffer rendezvous channel. This guarantees that no item is ever in-flight between stages without an active worker watching it.
    *   Use case: polling-heavy pipelines (e.g. OpenAI Batch API) where submitted jobs must never sit unmonitored in a queue.
    *   `workers=N` becomes a hard cap on items in-flight, with no `queue_capacity` tuning required.
    *   Incompatible with `retry="per_stage"`. Cannot be used on the first stage.
*   **`RendezvousChannel`:** The zero-buffer pull channel used internally by `pull=True` stages. Not part of the public API — use `pull=True` on a `Stage` instead.
*   **Call Concurrency (`call_concurrency` + `rate_limit()`):** New `Stage` parameter that limits concurrent API calls *within* long-running tasks. Unlike `task_concurrency_limits` (which limits how many tasks start), `call_concurrency` lets all workers run simultaneously but throttles specific calls wrapped by `async with rate_limit():`. Ideal for polling loops where many workers monitor jobs but only N API calls should happen at once.
    *   Set `call_concurrency=N` on the Stage.
    *   Wrap API calls inside the task with `async with rate_limit():`.
    *   Workers sleeping between polls do NOT hold a rate-limit slot.
    *   Exported: `from antflow.context import rate_limit` (also available as `from antflow import rate_limit`).
*   **`PullBatchPipeline` example:** `examples/openai_batch_prefetch.py` now contains two side-by-side implementations — the original sweeper-based `OpenAIBatchPipeline` and the new `PullBatchPipeline` — with a detailed docstring comparing when to use each. Updated to use `call_concurrency` instead of manual semaphores.
*   **`examples/pull_stage_openai_batch.py`:** Standalone example demonstrating `pull=True` + `call_concurrency` with an upload-prefetch buffer and a combined submit+poll stage.
*   **`examples/batch_api_simulation.py`:** Simulation script comparing different concurrency approaches (manual semaphore, `task_concurrency_limits`, `call_concurrency`) for the batch-API polling use case.
*   **Auto fast event loop:** The pipeline now automatically selects the fastest available event loop policy on supported platforms.

### Fixed

*   **`on_failure` not called in `per_stage` mode** — callback was silently skipped when `retry="per_stage"`.
*   **`on_success` fired for skipped items** — callback was incorrectly invoked even when `skip_if` returned `True`.
*   **`on_skip` not fired for skipped items** — callback was never invoked.
*   **`RendezvousChannel` race condition in `get()`** — when `put()` resolved a demand future in the same event-loop tick as a `wait_for` timeout, the item was lost and `join()` hung forever. Now if the future was resolved before the cancellation propagated, `get()` returns the value instead of re-raising.
*   **`RendezvousChannel` shutdown hang** — `put()` blocked forever when `close()` was called while a producer was waiting for demand. Now uses a `_closed` flag checked on each iteration of the `put()` loop.
*   **`shutdown()` silently discarded items** — now logs a `WARNING` with the count of discarded items.
*   **Deadlock in `per_stage` retry when `workers == queue_capacity`** — all workers could block simultaneously trying to re-queue retries into a full input queue. Retries now go through a dedicated unbounded overflow queue.
*   **`task_concurrency_limits` accepted unknown task names** — now raises `StageValidationError` at construction time instead of silently ignoring the limit.
*   **Task-level events not emitted in `per_stage` mode** — `on_task_start` / `on_task_complete` callbacks on `StatusTracker` were not fired.
*   **`stream()` ignored `buffer_size`** — the result queue was always unbounded regardless of the parameter.

### Changed

*   **Documentation:** `docs/user-guide/pipeline.md` expanded with Option C (pull=True) in the OpenAI Batch API use case section, including a comparison table between the sweeper, single-stage, and pull approaches.
*   **Test naming:** Regression tests renamed from `test_pipeline_bugs.py` to `test_pipeline_regressions.py` with behavior-based test function names.

## [0.7.3] - 2026-05-07

### Changed

*   **Release automation:** Added `scripts/release.sh` for consistent versioned releases.
*   **CI:** Strengthened release validation checks.

## [0.7.2] - 2026-01-15

### Added

*   **Configurable Dashboard Update Interval:** New `dashboard_update_interval` parameter in `Pipeline.run()`:
    *   Control how often dashboards update (default: 0.5s, changed from 0.1s)
    *   Recommended range: 0.1s to 1.0s
    *   Lower values = more responsive UI but higher CPU usage
    *   Higher values = lower CPU usage but less responsive UI
*   **Event-Driven Dashboard Example:** New `examples/custom_dashboard_callbacks.py` demonstrating:
    *   How to build custom dashboards using `StatusTracker` callbacks instead of polling
    *   Four practical examples: Simple, JSON stream, Multi-stage, and Task-level monitoring
    *   Direct comparison between polling and callback approaches
    *   Shows task-level monitoring (impossible with polling)

### Changed

*   **Dashboard Update Default:** Changed default update interval from 0.1s to 0.5s (2 updates/sec instead of 10)
    *   More efficient default for production use
    *   Reduces CPU overhead while maintaining good responsiveness
    *   Users can still configure faster updates via `dashboard_update_interval` parameter
*   **Enhanced Documentation:**
    *   Added comprehensive "How Polling Works" section in `docs/user-guide/custom-dashboard.md`
    *   Detailed explanation of `_monitor_progress` internal mechanism
    *   Clear guidance on when to use polling vs callbacks
    *   Performance notes and efficiency explanations
    *   Added prominent references to practical examples in documentation
*   **Improved `_monitor_progress` Documentation:** Added detailed docstring explaining:
    *   How the polling mechanism works
    *   Performance characteristics
    *   Efficiency considerations
    *   No "empty events" - only reads existing state

### Documentation

*   **Better Example Discovery:** Updated `docs/examples/index.md` with clearer descriptions:
    *   Explicitly marked `monitoring_status_tracker.py` as "Callbacks & Event-Driven Monitoring"
    *   Added `custom_dashboard_callbacks.py` to dashboards section
    *   Improved descriptions to make it easier to find callback examples
*   **Added TIP Boxes:** Prominent callouts in documentation pointing to practical examples:
    *   `custom-dashboard.md` now has clear references to both polling and callback examples
    *   `dashboard.md` includes link to comprehensive callback example

## [0.7.1] - 2026-01-15

### Added

*   **Internal Task Status Updates:** New `set_task_status()` function for real-time status updates within long-running tasks:
    *   Updates dashboard in real-time without waiting for task completion
    *   Perfect for polling scenarios (e.g., OpenAI batch processing)
    *   Optional `min_interval` parameter for rate limiting updates
    *   Accessible via `WorkerState.current_task` in custom dashboards
*   **New Example:** `examples/task_status_complete.py` - Comprehensive example demonstrating:
    *   Basic status updates
    *   Real-world polling with multiple API calls
    *   Rate limiting strategies
    *   Custom dashboard integration

### Changed

*   **Context Module:** Added `antflow.context` module with `worker_state_var` for thread-safe worker state access
*   **Documentation:** Enhanced `docs/user-guide/pipeline.md` with "Internal Task Status Updates" section including:
    *   Problem/solution explanation
    *   Usage examples with both `Pipeline.create()` and `Stage`
    *   Rate limiting best practices
    *   Custom dashboard integration guide

## [0.7.0] - 2026-01-15

### Added

*   **Dashboard Task Visibility:** Dashboard now shows the specific task (`current_task`) each worker is executing.
*   **Integrated Error Monitoring:** `DashboardSnapshot` now natively includes `error_summary` for immediate access to failure details.
*   **Web Dashboard Enhancements:**
    *   Added **Recent Errors** panel showing detailed failure logs (ID, stage, type, message).
    *   Added **Interactive Toggle Button** (Start/Stop) with automatic state synchronization.
    *   Persistence support: Closing and reopening the tab now resumes monitoring accurately.

### Changed

*   **Hard Stop Support:** `Pipeline.shutdown()` now forcefully stops workers after their current task and drains all queues to ensure immediate cessation of processing.
*   **Worker State:** `WorkerState` now includes a `current_task` field for better visibility into long-running stages with multiple tasks.

### Fixed

*   **Worker Idle Status on Shutdown:** Fixed an issue where workers remained in "busy" state on the UI after a manual stop.

## [0.6.1] - 2026-01-05

### Removed

*   **PipelineDashboard Class:** Removed the legacy `PipelineDashboard` helper class (in `antflow/dashboard.py`). It was redundant with the new built-in dashboard system and `DashboardProtocol`. Custom dashboards should now use `pipeline.get_dashboard_snapshot()` directly or implement `DashboardProtocol`.
*   **Stage Presets:** Removed `Stage.io_bound()`, `Stage.cpu_bound()`, and `Stage.rate_limited()`. Users should now use the generic `Stage` class and configure parameters manually for better explicit control.

## [0.6.0] - 2026-01-02

### Added

*   **Built-in Progress Bar:** Added `progress=True` parameter to `Pipeline.run()` for minimal terminal progress visualization.
*   **Dashboard System:** Three built-in dashboard levels via `dashboard` parameter:
    *   `"compact"`: Single panel with progress, rate, ETA, and counts.
    *   `"detailed"`: Per-stage metrics and worker performance.
    *   `"full"`: Complete monitoring with worker status and item tracking.
*   **Custom Dashboards:** Added `DashboardProtocol` for implementing custom dashboards via `custom_dashboard` parameter.
*   **Pipeline.quick():** One-liner API for simple pipelines.
    *   Single task: `await Pipeline.quick(items, process, workers=5)`
    *   Multiple tasks: `await Pipeline.quick(items, [fetch, process, save], workers=5)`
*   **Pipeline Builder:** Fluent API via `Pipeline.create()`:
    *   Chain `.add()` calls to build stages.
    *   Configure with `.with_tracker()` and `.collect_results()`.
    *   Execute with `.run()` or `.build()`.
*   **Stage Presets:** Pre-configured stage constructors:
    *   `Stage.io_bound()`: 10 workers, 3 retries (API calls, file I/O).
    *   `Stage.cpu_bound()`: CPU count workers, 1 retry (computation).
    *   `Stage.rate_limited()`: Enforced RPS limit (rate-limited APIs).
*   **Result Streaming:** `Pipeline.stream()` async iterator for processing results as they complete.
*   **Error Summary:** `get_error_summary()` method on Pipeline and StatusTracker:
    *   Aggregated error statistics by type and stage.
    *   Detailed `FailedItem` list with error details.
*   **New Types:**
    *   `ErrorSummary`: Aggregated error information.
    *   `FailedItem`: Individual failure details.
    *   `DashboardProtocol`: Interface for custom dashboards.
*   **New Display Module:** `antflow.display` with:
    *   `ProgressDisplay`: Minimal terminal progress bar.
    *   `CompactDashboard`: Rich-based compact dashboard.
    *   `DetailedDashboard`: Rich-based detailed dashboard.
    *   `FullDashboard`: Rich-based full monitoring dashboard.
    *   `BaseDashboard`: Abstract base for custom dashboards.
*   **New Examples:**
    *   `basic_example.py`: Shows all 3 ways to create pipelines (Stage, Builder, Quick).
    *   `builder_pattern.py`: Fluent builder API usage.
    *   `stage_presets.py`: Stage preset class methods.
    *   `streaming_results.py`: Pipeline.stream() usage.
    *   `dashboard_levels.py`: Comparing dashboard options.
    *   `custom_dashboard.py`: Custom dashboard implementations.
    *   `web_dashboard/`: Complete FastAPI + WebSocket dashboard example.
*   **New Documentation:**
    *   `docs/user-guide/progress.md`: Progress bar guide.
    *   `docs/user-guide/custom-dashboard.md`: Custom dashboard guide.
    *   `docs/api/display.md`: Display module API reference.

### Changed

*   **Dependencies:** Added `rich>=13.0.0` as a required dependency for dashboard features.
*   **README:** Updated with new Quick Start section showcasing new APIs.
*   **Examples:** Improved `advanced_pipeline.py` to show both Stage and Builder approaches.

### Removed

*   `basic_pipeline.py`: Replaced by `basic_example.py`.
*   `rich_polling_dashboard.py`: Replaced by built-in `dashboard="detailed"`.
*   `rich_callback_dashboard.py`: Replaced by built-in `dashboard="full"`.

## [0.5.0] - 2025-01-02

### ⚠ BREAKING CHANGES

*   **AsyncExecutor.map() now returns List instead of AsyncIterator**
    *   `map()` now collects all results and returns `List[R]` directly, matching `concurrent.futures` behavior.
    *   For streaming results, use the new `map_iter()` method which returns `AsyncIterator[R]`.
    *   **Migration:** `async for result in executor.map(fn, items):` → `for result in await executor.map(fn, items):`
    *   For streaming: `async for result in executor.map_iter(fn, items):`
*   **Removed `max_concurrency` parameter from `map()` and `map_iter()`**
    *   Use `max_workers` on executor creation or explicit semaphores with `submit()` instead.

### Added

*   **AsyncExecutor.map_iter()**: New method for streaming results as `AsyncIterator`, preserving input order.

### Fixed

*   **Pipeline progress calculation**: Fixed bug where `items_processed` was incremented per stage instead of only when items completed the entire pipeline (caused 300% progress with 3 stages).

### Changed

*   **Examples reorganization**:
    *   Consolidated 4 monitoring examples into 2: `monitoring_status_tracker.py` and `monitoring_workers.py`.
    *   Renamed `skip_resume.py` → `resume_with_skip_if.py` for clarity.
    *   Renamed `wait_example.py` → `executor_wait_strategies.py` for clarity.
    *   Fixed private attribute access in `backpressure_demo.py` and `priority_demo.py` to use public APIs.

## [0.4.1] - 2024-12-17

### Added

*   **Task Events API**: New callbacks `on_task_start`, `on_task_complete`, `on_task_retry`, `on_task_fail` for granular task-level monitoring. Each callback receives a `TaskEvent` with `item_id`, `task_name`, `stage`, `worker`, `attempt`, and `timestamp`.

*   **Automatic Stage Naming**: Stages now get automatic names (`Stage-0`, `Stage-1`, etc.) if no `name` is provided. This ensures consistent worker identification across all stages.

*   **Pipeline Worker Tracking**: Added worker identification to status events. Events now include which worker processed each item, enabling per-worker monitoring.

*   **Documentation Improvements**:
    *   New Worker Tracking Guide (`docs/user-guide/worker-tracking.md`)
    *   Updated Pipeline API reference with worker tracking details
    *   Enhanced type definitions documentation

### Changed

*   **Worker Naming Convention**: Workers are now named `{stage_name}-W{index}` (e.g., `Fetch-W0`, `Process-W1`) for clear identification in multi-stage pipelines.

*   **StatusEvent Enhanced**: Added `worker` field to `StatusEvent` dataclass to track which worker processed each item.

### Fixed

*   **Worker ID Extraction**: Fixed worker identification in `StatusTracker` to correctly parse worker names from stage context.

## [0.4.0] - 2024-12-14

### Added

*   **Pipeline Dashboard**: New `PipelineDashboard` class for building interactive monitoring UIs:
    *   `get_snapshot()`: Returns complete pipeline state including worker states, metrics, and statistics
    *   `subscribe(callback)`: Register callbacks for real-time status change notifications
    *   Configurable `update_interval` for controlling snapshot frequency

*   **Dashboard Data Structures**: New types for comprehensive pipeline visibility:
    *   `DashboardSnapshot`: Complete point-in-time pipeline state
    *   `WorkerState`: Per-worker status (idle/busy, current item, processing time)
    *   `WorkerMetrics`: Per-worker performance (items processed, failures, avg time)
    *   `PipelineStats`: Aggregate statistics (items processed, failed, in-flight, queue sizes)

*   **Stage Callbacks**: New `on_success` and `on_failure` callbacks on `Stage`:
    *   `on_success(item_id, result, metadata)`: Called when item completes successfully
    *   `on_failure(item_id, error, metadata)`: Called when item fails all retries
    *   Enables custom logic like logging, metrics collection, or external notifications

*   **Per-Task Concurrency Limits**: New `task_concurrency_limits` parameter on `Stage`:
    *   Limit specific tasks independently (e.g., rate-limit API calls while allowing parallel processing)
    *   Uses semaphores internally for precise control
    *   Example: `task_concurrency_limits={"call_api": 5}` limits `call_api` to 5 concurrent calls

*   **Examples**:
    *   `rich_polling_dashboard.py`: Real-time terminal dashboard using Rich library with polling
    *   `rich_callback_dashboard.py`: Event-driven dashboard using callbacks
    *   `dashboard_websocket.py`: WebSocket integration pattern for browser-based dashboards

### Changed

*   **StatusTracker Performance**: Improved memory efficiency by limiting history storage per item

### Fixed

*   **Worker State Tracking**: Fixed race condition in worker state updates during high concurrency

## [0.3.0] - 2024-12-13

### Added

*   **Interactive Pipeline Control**: New methods for dynamic pipeline manipulation:
    *   `Pipeline.feed(items, target_stage, priority)`: Inject items at runtime into any stage
    *   `Pipeline.wait(item_ids, return_when)`: Wait for specific items (ALL_COMPLETED, FIRST_COMPLETED, FIRST_EXCEPTION)
    *   Enables producer-consumer patterns and interactive processing

*   **Priority Queue Support**: Items can now be assigned priority levels:
    *   Lower numbers = higher priority (0 is highest)
    *   Default priority is 100
    *   High-priority items are processed before lower-priority ones

*   **Resume Capability**: Skip already-processed items with new `skip_if` parameter:
    *   `skip_if`: Async function `(payload) -> bool` to check if item should be skipped
    *   Enables resumable pipelines after failures

*   **StatusTracker Enhancements**:
    *   `get_status(item_id)`: Query current status of any item
    *   `get_by_status(status)`: Get all items with a specific status
    *   `get_stats()`: Get counts by status (completed, failed, in_progress, queued)
    *   `get_history(item_id)`: Get full event history for an item

*   **Examples**: New examples demonstrating:
    *   `priority_demo.py`: Priority-based processing
    *   `resume_checkpoint.py`: Resumable pipelines with checkpoints
    *   `skip_resume.py`: Using `skip_if` for resume capability
    *   `producer_consumer.py`: Dynamic item feeding patterns

### Changed

*   **Pipeline Architecture**: Internal refactoring for interactive control support
*   **Queue Implementation**: Switched to priority queue for all stages

## [0.2.0] - 2024-12-12

### Added

*   **StatusTracker**: Real-time item status tracking with callbacks:
    *   Track item status: queued, in_progress, completed, failed
    *   `on_status_change` callback for real-time monitoring
    *   Metadata support for tracking retry attempts

*   **Retry Strategies**: Two retry modes for `Stage`:
    *   `retry="per_task"`: Retry individual tasks within a stage (default)
    *   `retry="per_stage"`: Retry entire stage as a unit (for transactional operations)
    *   Configurable attempts and wait times

*   **Pipeline Context Manager**: Use `async with Pipeline(...) as pipeline:` for automatic cleanup

*   **Examples**: Multiple examples demonstrating various features

### Changed

*   **Stage Configuration**: Added `retry`, `task_attempts`, `task_wait_seconds`, `stage_attempts`, `stage_wait_seconds` parameters

## [0.1.0] - 2024-12-11

### Added

*   **AsyncExecutor**: Drop-in async replacement for `concurrent.futures.ThreadPoolExecutor`:
    *   `submit(fn, *args, **kwargs)`: Submit single task
    *   `map(fn, items)`: Process multiple items in parallel
    *   `as_completed(futures)`: Iterate results as they complete
    *   `shutdown()`: Graceful shutdown

*   **Pipeline**: Multi-stage async processing pipeline:
    *   `Stage`: Configurable processing stage with worker pool
    *   Automatic data flow between stages
    *   Result collection with `PipelineResult`

*   **Error Handling**: Built-in retry with exponential backoff via tenacity

*   **Documentation**: Initial documentation with MkDocs
