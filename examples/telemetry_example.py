"""
OpenTelemetry Instrumentation Example for AntFlow

This example demonstrates how to enable, configure, and use OpenTelemetry
tracing and metrics in an AntFlow pipeline.

To run this example, install the opentelemetry extra and SDK:
    pip install ".[dev]"  # or: pip install AntFlow[opentelemetry] opentelemetry-sdk
"""

import asyncio
import random
import sys

from antflow import Pipeline, configure_telemetry, telemetry_enabled

# Set up OpenTelemetry Tracing and Metrics to write to Console
try:
    from opentelemetry import trace
    from opentelemetry import metrics
    
    # Trace setup
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
    
    # Metrics setup
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    
    OTEL_INSTALLED = True
except ImportError:
    OTEL_INSTALLED = False


def setup_telemetry():
    """Configure in-memory/console tracing and metrics providers."""
    if not OTEL_INSTALLED:
        print("[-] OpenTelemetry SDK is not installed. Running with No-Op placeholders.")
        return

    # Trace configuration
    trace_provider = TracerProvider()
    # SimpleSpanProcessor prints each span immediately upon completion to the console
    span_processor = SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout))
    trace_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(trace_provider)

    # Metrics configuration
    # Periodic reader reports metric snapshots to the console periodically
    metric_reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(out=sys.stdout),
        export_interval_millis=5000  # fast export for demo purposes
    )
    metric_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)
    
    print("[+] OpenTelemetry tracing and metrics configured with Console Exporter.")


async def fetch_item(item_id: int) -> dict:
    """Fetch task simulating web I/O request."""
    await asyncio.sleep(random.uniform(0.02, 0.05))
    return {"id": item_id, "data": f"content_{item_id}"}


async def process_item(item: dict) -> dict:
    """Process task simulating compute payload transformation."""
    await asyncio.sleep(random.uniform(0.01, 0.03))
    item["data"] = item["data"].upper()
    return item


async def main():
    print("=" * 70)
    print("AntFlow OpenTelemetry Tracing & Metrics Demo")
    print("=" * 70)

    # 1. Setup providers
    setup_telemetry()

    # 2. Check telemetry status
    print(f"Is Telemetry Enabled: {telemetry_enabled()}")
    print("=" * 70)

    # 3. Define and run pipeline
    items = list(range(3))
    print(f"\nRunning pipeline with {len(items)} items...")
    
    pipeline = (
        Pipeline.create()
        .add("FetchStage", fetch_item, workers=2)
        .add("ProcessStage", process_item, workers=2)
        .build()
    )
    
    results = await pipeline.run(items)
    print(f"\nPipeline finished. Processed {len(results)} items.")
    print("=" * 70)

    # 4. Show Toggle capability
    print("\nDisabling telemetry at runtime...")
    configure_telemetry(enabled=False)
    print(f"Is Telemetry Enabled now: {telemetry_enabled()}")
    
    print("\nRunning pipeline again (No spans should print to stdout)...")
    await pipeline.run([99])
    print("Pipeline run completed under disabled telemetry.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
