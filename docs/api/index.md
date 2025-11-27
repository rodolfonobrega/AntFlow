# API Reference

Welcome to the AntFlow API Reference. This documentation provides detailed information about the classes, functions, and types available in the library.

## Core Modules

| Module | Description |
|--------|-------------|
| **[Pipeline](pipeline.md)** | The heart of AntFlow. Contains `Pipeline` and `Stage` classes for building multi-step workflows. |
| **[StatusTracker](tracker.md)** | Observability layer. Contains `StatusTracker` and event definitions for real-time monitoring. |
| **[AsyncExecutor](executor.md)** | Simple concurrent execution. Contains `AsyncExecutor` (like `concurrent.futures`) and `AsyncFuture`. |

## Support Modules

| Module | Description |
|--------|-------------|
| **[Types](types.md)** | Data structures and type definitions (`TaskEvent`, `WorkerMetrics`, etc.). |
| **[Utils](utils.md)** | Helper functions for logging and error handling. |
| **[Exceptions](exceptions.md)** | The exception hierarchy used throughout the library. |
