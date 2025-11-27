# Examples Index

This directory contains a comprehensive list of example scripts available in the `examples/` directory of the repository. These scripts demonstrate various features and patterns of AntFlow.

## Basic Usage

| Example | Description |
|---------|-------------|
| **[basic_executor.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/basic_executor.py)** | Simple usage of `AsyncExecutor` for concurrent task execution. |
| **[basic_pipeline.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/basic_pipeline.py)** | Basic `Pipeline` setup with sequential stages. |
| **[wait_example.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/wait_example.py)** | Demonstrates different `WaitStrategy` options (`ALL_COMPLETED`, `FIRST_COMPLETED`, etc.). |

## Pipeline Patterns

| Example | Description |
|---------|-------------|
| **[advanced_pipeline.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/advanced_pipeline.py)** | Complex pipeline with multiple stages, retries, and error handling. |
| **[real_world_example.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/real_world_example.py)** | A realistic ETL scenario simulating data ingestion, processing, and storage. |

## Monitoring & Tracking

| Example | Description |
|---------|-------------|
| **[status_tracking.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/status_tracking.py)** | Basic usage of `StatusTracker` to monitor item progress. |
| **[task_level_tracking.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/task_level_tracking.py)** | Granular tracking of individual task execution events. |
| **[worker_tracking.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/worker_tracking.py)** | Monitoring the state and activity of individual workers. |
| **[worker_monitoring.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/worker_monitoring.py)** | Advanced worker monitoring patterns. |

## Dashboards

| Example | Description |
|---------|-------------|
| **[rich_dashboard.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/rich_dashboard.py)** | **Recommended**: A beautiful, real-time terminal dashboard using the `rich` library. |
| **[dashboard_websocket.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/dashboard_websocket.py)** | Example of serving pipeline metrics over a WebSocket for web dashboards. |

## Detailed Guides

For step-by-step explanations of these concepts, check out our guide pages:

- [Basic Examples](basic.md)
- [Advanced Examples](advanced.md)
