# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.6] - 2025-12-02

### Documentation

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
