# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
