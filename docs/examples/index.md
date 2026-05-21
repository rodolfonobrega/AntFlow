# Examples Index

This directory contains a comprehensive list of example scripts available in the `examples/` directory of the repository. These scripts demonstrate various features and patterns of AntFlow.

## Basic Usage

| Example | Description |
|---------|-------------|
| **[basic_executor.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/basic_executor.py)** | Simple usage of `AsyncExecutor` for concurrent task execution. |
| **[basic_example.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/basic_example.py)** | Basic `Pipeline` setup with sequential stages. |
| **[executor_wait_strategies.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/executor_wait_strategies.py)** | Demonstrates different `WaitStrategy` options for `AsyncExecutor`. |
| **[builder_pattern.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/builder_pattern.py)** | Using the `PipelineBuilder` (Fluent API) to construct pipelines. |

## Pipeline Patterns

| Example | Description |
|---------|-------------|
| **[advanced_pipeline.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/advanced_pipeline.py)** | Complex pipeline with multiple stages, retries, and error handling. |
| **[real_world_example.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/real_world_example.py)** | A realistic ETL scenario simulating data ingestion, processing, and storage. |
| **[streaming_results.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/streaming_results.py)** | Processing results as they complete using the `stream()` method. |
| **[priority_demo.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/priority_demo.py)** | Handling task priorities (Low/High) in the pipeline queue. |
| **[task_limits_openai.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/task_limits_openai.py)** | **New**: Managing strict API rate limits using `task_concurrency_limits`. |
| **[backpressure_demo.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/backpressure_demo.py)** | **New**: Demonstrating automatic backpressure and queue capacity limits. |
| **[resume_checkpoint.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/resume_checkpoint.py)** | Manual checkpointing and resuming pipeline execution from a specific point. |
| **[openai_batch_prefetch.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/openai_batch_prefetch.py)** | OpenAI Batch API pipeline with upload prefetch. Contains two implementations side-by-side: sweeper-based (`OpenAIBatchPipeline`) and pull-based (`PullBatchPipeline`). See [pipeline guide](../user-guide/pipeline.md#option-c-two-stages--pulltrue-upload-prefetch--exact-control-) for a detailed comparison. |

## Monitoring & Tracking

| Example | Description |
|---------|-------------|
| **[monitoring_status_tracker.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/monitoring_status_tracker.py)** | **Callbacks & Event-Driven Monitoring** - Complete example using `StatusTracker` with `on_status_change` and task-level callbacks (`on_task_start`, `on_task_complete`, `on_task_retry`, `on_task_fail`). |
| **[monitoring_workers.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/monitoring_workers.py)** | Monitoring the state and activity of individual workers. |

## Dashboards

| Example | Description |
|---------|-------------|
| **[dashboard_levels.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/dashboard_levels.py)** | **Recommended**: Comparing `compact`, `detailed`, and `full` built-in dashboards. |
| **[custom_dashboard.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/custom_dashboard.py)** | Implementing custom dashboards using `DashboardProtocol` (polling-based). |
| **[custom_dashboard_callbacks.py](https://github.com/rodolfonobrega/antflow/blob/main/examples/custom_dashboard_callbacks.py)** | **NEW**: Implementing custom dashboards using `StatusTracker` callbacks (event-driven alternative). |
| **[web_dashboard/](https://github.com/rodolfonobrega/antflow/blob/main/examples/web_dashboard/)** | Complete FastAPI + WebSocket dashboard for web browsers. |

## Detailed Guides

For step-by-step explanations of these concepts, check out our guide pages:

- [Basic Examples](basic.md)
- [Advanced Examples](advanced.md)
- [Pipeline Guide](../user-guide/pipeline.md)
- [Dashboard Guide](../user-guide/dashboard.md)
