# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2025-01-02

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
    *   `quick_api.py`: Pipeline.quick() demonstrations.
    *   `builder_pattern.py`: Fluent builder API usage.
    *   `stage_presets.py`: Stage preset class methods.
    *   `streaming_results.py`: Pipeline.stream() usage.
    *   `dashboard_levels.py`: Comparing dashboard options.
    *   `custom_dashboard.py`: Custom dashboard implementations.
*   **New Documentation:**
    *   `docs/user-guide/progress.md`: Progress bar guide.
    *   `docs/user-guide/custom-dashboard.md`: Custom dashboard guide.
    *   `docs/api/display.md`: Display module API reference.

### Changed

*   **Dependencies:** Added `rich>=13.0.0` as a required dependency for dashboard features.
*   **README:** Updated with new Quick Start section showcasing new APIs.

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
    *   Added comprehensive docstrings to all examples.
    *   Fixed `result['id']` → `result.id` in `basic_pipeline.py`, `advanced_pipeline.py`, `real_world_example.py`.
*   **Rich dashboards**: Refactored `rich_polling_dashboard.py` and `rich_callback_dashboard.py` to display identical information using different approaches (polling vs callback).
*   **Code quality**: Applied ruff fixes (unused imports, import ordering, whitespace cleanup).

## [0.4.1] - 2025-12-17

### Added
- **Smart Queue Limits**: Pipelines now automatically enforce backpressure. Stage input queues default to a capacity of `workers * 10`, preventing memory exhaustion automatically.
- New `queue_capacity` parameter in `Stage` to override the default limit.

## [0.4.0] - 2025-12-10

### ⚠ BREAKING CHANGES

*   **Internal Queue Structure:** The pipeline now uses `asyncio.PriorityQueue` instead of `asyncio.Queue`.
    *   Items in the queue are now tuples `(priority, sequence, item)`.
    *   Subclasses accessing `_queues` directly will need to adapt.

### Added

*   **Feature: Conditional Stage Skipping**
    *   `Stage` now accepts a `skip_if` callable (e.g., `lambda x: x.is_done`).
    *   Items meeting the condition skip processing and are passed directly to the next stage with a `skipped` status.
    *   Ideal for "resume from start" strategies.
    *   **Example:** Added `examples/skip_resume.py`.
*   **Feature: Stage Metrics**
    *   `Pipeline.get_stats()` now returns granular `stage_stats`, including pending, in-progress, completed, and failed counts per stage.
    *   Updated `examples/rich_polling_dashboard.py` to visualize these stage-level metrics.
*   **Feature: Interactive Pipeline Lifecycle**
    *   Added `Pipeline.start()`: Initializes and starts workers without blocking.
    *   Added `Pipeline.join()`: Waits for all items to be processed and shuts down.
    *   Updated `Pipeline.feed()`: Now accepts a `target_stage` argument to inject items directly into specific stages.
    *   **Resume Capability:** The combination of these features allows users to "resume" pipelines by injecting items into the specific stages where they left off.
*   **Feature: Priority Queues**
    *   `Pipeline.feed()` and `Pipeline.feed_async()` now accept a `priority` parameter (int).
    *   Default priority is 100. Lower numbers = Higher Priority.
    *   Allows urgent items to "jump the line" of waiting tasks.
*   **Documentation:** Added "Interactive Execution" and "Priority Queues" sections to `docs/user-guide/pipeline.md` explaining the new workflows.
*   **Example:** Added `examples/resume_checkpoint.py` and `examples/priority_demo.py` demonstrating the new capabilities.
*   **Documentation:**
    *   Added dedicated **Concurrency Control Guide** (`docs/user-guide/concurrency.md`).
    *   Fixed incorrect example in `pipeline.md` where `task_concurrency_limits` was placed in `StatusTracker`.
    *   Updated `executor.md` to link to the new concurrency guide.

## [0.3.5] - 2025-12-02

### Added

*   **Concurrency Control:**
    *   Added `max_concurrency` parameter to `AsyncExecutor.map` to limit concurrent executions within a map operation.
    *   Added `semaphore` parameter to `AsyncExecutor.submit` for manual concurrency control across tasks.
    *   Added `task_concurrency_limits` to `Stage` class to limit concurrency of specific tasks within a pipeline stage.
*   **Retry Improvements:**
    *   Changed retry mechanism to use **exponential backoff** by default. `retry_delay` now serves as the initial multiplier.

## [0.3.4] - 2025-11-28

### Fixed

*   **Changelog:** Corrected changelog history for versions 0.3.2 and 0.3.3.

## [0.3.3] - 2025-11-28

### Added

*   **Feature:** Added retry logic to `AsyncExecutor.map` and `AsyncExecutor.submit`.
    *   `submit` now accepts `retries` and `retry_delay` arguments.
    *   `map` now accepts `retries` and `retry_delay` arguments.

## [0.3.2] - 2025-11-28

### Added

*   **Feature:** Added `retrying` status to `StatusType` and `StatusEvent`.
    *   This status is emitted when an item fails in a stage and is queued for a retry (when using `retry="per_stage"`).
    *   This improves observability by distinguishing between initial queuing and retry queuing.
*   **Example:** Updated `examples/rich_polling_dashboard.py` to visualize the `retrying` status with a distinct color.

## [0.3.1] - 2025-11-27

### ⚠ BREAKING CHANGES

*   **Refactor:** `Pipeline.run()` and `Pipeline.results` now return a list of `PipelineResult` objects instead of dictionaries.
    *   This provides better type safety and IDE autocomplete.
    *   **Migration:** Change `result['value']` to `result.value`, `result['id']` to `result.id`, etc.

### Added

*   **Feature:** Added `on_success` and `on_failure` callbacks to `Stage` class for custom event handling per stage.
*   **Types:** Added `PipelineResult` dataclass to `antflow.types` to structure pipeline output.

### Changed

*   **Documentation:** Fixed broken examples in `README.md` and `docs/examples/advanced.md` to be self-contained and executable.
*   **Cleanup:** Removed unused `OrderedResult` class from `antflow.types`.

## [0.3.0] - 2025-11-27

### ⚠ BREAKING CHANGES

*   **Refactor:** `StatusEvent` class has been moved from `antflow.tracker` to `antflow.types`.
    *   If you were importing `StatusEvent` directly from `antflow.tracker`, you must update your imports to `antflow.types` or `antflow` (if exposed in top-level init).
    *   Example: `from antflow.tracker import StatusEvent` -> `from antflow.types import StatusEvent`

### Added

*   **Types:** `StatusEvent` is now available in `antflow.types` module.

### Changed

*   **Refactor:** Moved `StatusEvent` definition to `antflow/types.py` to avoid circular imports and centralize type definitions.
*   **Documentation:** Updated docstrings in `StatusTracker` to correctly reference `StatusEvent` and `TaskEvent` in `antflow.types`.
*   **Cleanup:** Removed `test_output.txt` from the repository to keep the distribution clean.
