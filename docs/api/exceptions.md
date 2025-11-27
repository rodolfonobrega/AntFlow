# Exceptions API

The `antflow.exceptions` module defines the custom exception hierarchy used by AntFlow.

## Overview

All exceptions inherit from the base `AntFlowError`. This allows you to catch any AntFlow-related error with a single `except` block.

## Exception Hierarchy

- **`AntFlowError`**: Base class for all exceptions.
    - **`ExecutorShutdownError`**: Raised when attempting to submit tasks to an `AsyncExecutor` that has already been shut down.
    - **`PipelineError`**: Base class for pipeline-related errors.
        - **`StageValidationError`**: Raised when a `Stage` is configured incorrectly (e.g., invalid worker count, unknown retry policy).
    - **`TaskFailedError`**: Wraps an original exception when a task fails. Contains the `task_name` and the `original_exception`.

## Exception Reference

For the complete exception definitions, see the [source code](../../antflow/exceptions.py).
