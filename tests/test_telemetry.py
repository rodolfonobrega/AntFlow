import asyncio
import pytest
from unittest import mock

from antflow import (
    Pipeline,
    AsyncExecutor,
    configure_telemetry,
    telemetry_enabled,
)
from antflow.telemetry import _HAS_OTEL, get_tracer, get_meter

# Try to import SDK elements to test actual OTel propagation
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


# Setup global tracing and metrics providers once for the session
GLOBAL_EXPORTER = None
GLOBAL_METRIC_READER = None

if SDK_AVAILABLE:
    # Tracing
    trace_provider = TracerProvider()
    GLOBAL_EXPORTER = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(GLOBAL_EXPORTER)
    trace_provider.add_span_processor(span_processor)
    otel_trace.set_tracer_provider(trace_provider)

    # Metrics
    GLOBAL_METRIC_READER = InMemoryMetricReader()
    metric_provider = MeterProvider(metric_readers=[GLOBAL_METRIC_READER])
    otel_metrics.set_meter_provider(metric_provider)


@pytest.fixture(autouse=True)
def reset_telemetry():
    """Ensure telemetry starts enabled and OTel exports are cleared before each test."""
    configure_telemetry(enabled=True)
    if SDK_AVAILABLE and GLOBAL_EXPORTER:
        GLOBAL_EXPORTER.clear()
    yield
    configure_telemetry(enabled=True)


def test_toggle_telemetry():
    """Test that configuring telemetry toggle updates its status correctly."""
    if not _HAS_OTEL:
        assert not telemetry_enabled()
        return

    configure_telemetry(enabled=True)
    assert telemetry_enabled() is True

    configure_telemetry(enabled=False)
    assert telemetry_enabled() is False


@pytest.mark.asyncio
async def test_noop_telemetry_when_disabled():
    """Verify that when disabled, tracer and meter return no-op versions and no exceptions are raised."""
    configure_telemetry(enabled=False)
    
    tracer = get_tracer()
    meter = get_meter()
    
    assert hasattr(tracer, "start_span")
    assert hasattr(tracer, "start_as_current_span")
    assert hasattr(meter, "create_counter")
    
    # Run a pipeline and verify no-op context doesn't crash
    async def sample_task(x):
        return x * 2

    pipeline = Pipeline.create().add("TestStage", sample_task, workers=1).build()
    results = await pipeline.run([1, 2, 3])
    assert len(results) == 3
    assert [r.value for r in results] == [2, 4, 6]


@pytest.mark.skipif(not SDK_AVAILABLE, reason="opentelemetry-sdk not installed")
@pytest.mark.asyncio
async def test_otel_span_propagation():
    """Test that pipeline execution creates the expected trace hierarchy (pipeline -> stage -> task)."""
    async def sample_task(x):
        await asyncio.sleep(0.01)
        return x + 1

    pipeline = Pipeline.create().add("StageOne", sample_task, workers=2).build()
    await pipeline.run([10, 20])
    
    spans = GLOBAL_EXPORTER.get_finished_spans()
    
    # Should have: 1 pipeline span, 2 stage spans (one per item), 2 task spans (one per item)
    assert len(spans) >= 5
    
    # Find pipeline span
    pipeline_spans = [s for s in spans if s.name == "antflow.pipeline.run"]
    assert len(pipeline_spans) == 1
    pipeline_span = pipeline_spans[0]
    assert pipeline_span.attributes.get("antflow.pipeline.total_items") == 2
    assert pipeline_span.attributes.get("antflow.pipeline.stages") == 1
    
    # Stage spans should have pipeline_span as parent
    stage_spans = [s for s in spans if s.name == "antflow.stage.StageOne"]
    assert len(stage_spans) == 2
    for stage_span in stage_spans:
        assert stage_span.parent.span_id == pipeline_span.context.span_id
        assert stage_span.attributes.get("antflow.stage.name") == "StageOne"
        
        # Task spans should have their respective stage_span as parent
        task_spans = [s for s in spans if s.name == "antflow.task.sample_task" and s.parent.span_id == stage_span.context.span_id]
        assert len(task_spans) == 1
        task_span = task_spans[0]
        assert task_span.attributes.get("antflow.task.name") == "sample_task"
        assert task_span.attributes.get("antflow.task.attempt") == 1


@pytest.mark.skipif(not SDK_AVAILABLE, reason="opentelemetry-sdk not installed")
@pytest.mark.asyncio
async def test_otel_span_error_recording():
    """Verify that exceptions inside tasks are correctly recorded on OTel spans."""
    async def failing_task(x):
        raise ValueError("Intentional task failure")

    # set retries to 1 (1 task attempt)
    pipeline = Pipeline.create().add("FailingStage", failing_task, workers=1, retries=1).build()
    await pipeline.run([1])
    
    spans = GLOBAL_EXPORTER.get_finished_spans()
    
    # Look for task span
    task_spans = [s for s in spans if s.name == "antflow.task.failing_task"]
    assert len(task_spans) == 1
    task_span = task_spans[0]
    
    # Span should be marked as Error status and have the exception event
    assert task_span.status.status_code == otel_trace.StatusCode.ERROR
    assert "Intentional task failure" in task_span.status.description
    assert len(task_span.events) >= 1
    assert task_span.events[0].name == "exception"


@pytest.mark.skipif(not SDK_AVAILABLE, reason="opentelemetry-sdk not installed")
@pytest.mark.asyncio
async def test_otel_metrics():
    """Test that pipeline execution updates the OTel metrics (processed, failed, retried)."""
    # Create a pipeline with retries=2 so that we trigger a retry
    retry_count = 0
    async def retry_task(x):
        nonlocal retry_count
        if x == 0 and retry_count == 0:
            retry_count += 1
            raise ValueError("Retry me")
        return x
        
    pipeline = Pipeline.create().add("MetricStage", retry_task, workers=1, retries=2).build()
    await pipeline.run([0])
    
    metrics_data = GLOBAL_METRIC_READER.get_metrics_data()
    assert metrics_data is not None
    
    metric_names = []
    for rm in metrics_data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                metric_names.append(metric.name)
                
    assert "antflow.pipeline.items.processed" in metric_names
    assert "antflow.pipeline.items.retried" in metric_names
    assert "antflow.task.duration" in metric_names


@pytest.mark.skipif(not SDK_AVAILABLE, reason="opentelemetry-sdk not installed")
@pytest.mark.asyncio
async def test_executor_spans():
    """Verify AsyncExecutor creates trace spans for task executions."""
    async def calc(x):
        return x * x

    async with AsyncExecutor(max_workers=2) as executor:
        results = await executor.map(calc, [2, 3])
        assert results == [4, 9]

    spans = GLOBAL_EXPORTER.get_finished_spans()
    executor_spans = [s for s in spans if s.name == "antflow.executor.task"]
    assert len(executor_spans) == 2
    for span in executor_spans:
        assert "antflow.executor.worker_id" in span.attributes
        assert "antflow.executor.task_id" in span.attributes
