# OpenTelemetry Integration

AntFlow provides built-in, out-of-the-box support for **OpenTelemetry (OTel)** tracing and metrics. When enabled, it automatically instruments pipeline runs, stages, tasks, and `AsyncExecutor` worker executions.

Telemetry is implemented as an **optional dependency**. If you do not install the telemetry packages or explicitly disable it, AntFlow uses zero-overhead no-op wrappers, ensuring no performance penalty or dependency bloat.

---

## Installation

To install AntFlow with OpenTelemetry support, use the `opentelemetry` extra:

```bash
pip install AntFlow[opentelemetry]
```

This installs the required `opentelemetry-api` package. You will need to install and configure an OpenTelemetry SDK (such as `opentelemetry-sdk` and exporters like `opentelemetry-exporter-otlp`) in your application to collect and view the telemetry data.

---

## Tracing

When OpenTelemetry is active, AntFlow creates a span hierarchy that mirrors your pipeline's structure:

*   **Pipeline Run (`antflow.pipeline.run`)**: Created for the duration of `Pipeline.run()`. Contains overview metrics such as total item counts and stage configurations.
*   **Stage Span (`antflow.stage.<StageName>`)**: Nested under the pipeline run, created for each item flowing through a specific stage.
*   **Task Span (`antflow.task.<task_name>`)**: Nested under the stage span, created for each individual task function execution. Task attempts and retries are represented here.
*   **Executor Task Span (`antflow.executor.task`)**: Created for task executions run via `AsyncExecutor`.

### Span Attributes

#### Pipeline Spans
*   `antflow.pipeline.total_items`: Total number of items submitted.
*   `antflow.pipeline.stages`: Number of stages in the pipeline.
*   `antflow.pipeline.stage_names`: List of stage names.
*   `antflow.pipeline.items_processed`: Number of successfully completed items.
*   `antflow.pipeline.items_failed`: Number of failed items.

#### Stage Spans
*   `antflow.stage.name`: Name of the stage.
*   `antflow.worker.name`: Name of the worker processing the item.
*   `antflow.item.id`: Unique identifier of the item.
*   `antflow.item.attempt`: Current attempt number of the item.

#### Task Spans
*   `antflow.task.name`: Name of the task function.
*   `antflow.task.attempt`: Current attempt number of the task.
*   `antflow.worker.name`: Name of the worker executing the task.
*   `antflow.stage.name`: Stage to which this task belongs.

#### Executor Task Spans
*   `antflow.executor.worker_id`: Worker processing the task.
*   `antflow.executor.task_id`: Monotonically increasing identifier of the task.

---

## Metrics

AntFlow records several key metrics during execution. If an OTel Meter Provider is configured, the following metrics will be emitted:

| Metric Name | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `antflow.pipeline.items.processed` | Counter | `1` | Count of successfully processed items. |
| `antflow.pipeline.items.failed` | Counter | `1` | Count of failed items. |
| `antflow.pipeline.items.retried` | Counter | `1` | Count of item/task retry attempts. |
| `antflow.task.duration` | Histogram | `s` | Task execution duration distribution. |

---

## Controlling Telemetry

You can globally enable or disable telemetry at runtime using the `configure_telemetry` function:

```python
from antflow import configure_telemetry

# Disable all OpenTelemetry tracing and metrics
configure_telemetry(enabled=False)

# Re-enable
configure_telemetry(enabled=True)
```

To check if telemetry is currently active:

```python
from antflow import telemetry_enabled

if telemetry_enabled():
    print("OpenTelemetry instrumentation is active!")
```

---

## Basic Configuration Example

Here is a simple example showing how to set up an in-memory/console SDK exporter and run a pipeline with tracing active:

```python
import asyncio
from antflow import Pipeline, configure_telemetry

# 1. Configure OpenTelemetry SDK
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# 2. Define tasks
async def fetch(x):
    await asyncio.sleep(0.05)
    return f"raw_{x}"

async def process(x):
    await asyncio.sleep(0.02)
    return x.upper()

# 3. Build and execute pipeline (telemetry is auto-enabled)
async def main():
    results = await (
        Pipeline.create()
        .add("Fetch", fetch, workers=2)
        .add("Process", process, workers=2)
        .run([1, 2])
    )
    
if __name__ == "__main__":
    asyncio.run(main())
```
