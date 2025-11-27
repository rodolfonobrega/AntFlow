# Utilities API

Helper functions and utilities used internally by AntFlow.

## Overview

The `antflow.utils` module provides standardized logging and error handling utilities.

## Functions

### setup_logger

```python
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger
```

Configures a logger with a consistent format (`%(asctime)s | %(levelname)s | %(message)s`). This ensures all AntFlow components log in a readable, uniform way.

### extract_exception

```python
def extract_exception(error: Exception) -> Exception
```

Helper to unwrap exceptions wrapped by `tenacity.RetryError`. When a task fails after retries, `tenacity` wraps the original error. This function retrieves the underlying cause, making error logs much cleaner.

## Function Reference

For the complete function signatures, see the [source code](../../antflow/utils.py).
