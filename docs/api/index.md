# API Reference

Complete API documentation for AntFlow, auto-generated from source code docstrings.

## Modules

- [Executor](executor.md) - AsyncExecutor and AsyncFuture classes
- [Pipeline](pipeline.md) - Pipeline and Stage classes
- [Types](types.md) - Type definitions and protocols
- [Exceptions](exceptions.md) - Exception hierarchy
- [Utilities](utils.md) - Helper functions

## Quick Links

### Core Classes

- **AsyncExecutor** - Concurrent.futures-style async executor
- **AsyncFuture** - Future representing async task result
- **Pipeline** - Multi-stage processing pipeline
- **Stage** - Pipeline stage configuration

### Type Definitions

- **TaskFunc** - Async task callable type
- **CallbackFunc** - Stage-level callback type
- **TaskCallbackFunc** - Task-level callback type
- **PipelineStats** - Pipeline metrics dataclass

### Exceptions

- **AntFlowError** - Base exception
- **ExecutorShutdownError** - Executor shutdown errors
- **PipelineError** - Pipeline-specific errors
- **StageValidationError** - Stage configuration errors
- **TaskFailedError** - Task failure wrapper

## Usage

Each module page provides detailed documentation including:

- Class and function signatures
- Parameter descriptions
- Return values
- Exception information
- Usage examples

Navigate using the sidebar or the links above.
