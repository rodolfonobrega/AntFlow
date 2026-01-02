# Custom Dashboard Guide

AntFlow allows you to create custom dashboards by implementing the `DashboardProtocol`.

## Built-in vs Custom Dashboards

AntFlow provides built-in dashboards for common use cases:

```python
# Simple progress bar (no Rich dependency)
results = await pipeline.run(items, progress=True)

# Built-in Rich dashboards
results = await pipeline.run(items, dashboard="compact")   # Single panel
results = await pipeline.run(items, dashboard="detailed")  # Per-stage table
results = await pipeline.run(items, dashboard="full")      # Full monitoring
```

For custom visualization needs, you can implement your own dashboard.

## Two Approaches: Polling vs Callbacks

| Approach | Use Case | How it Works |
|----------|----------|--------------|
| **DashboardProtocol** (polling) | Terminal UIs, web dashboards | `on_update()` called periodically with full state |
| **StatusTracker callbacks** (event-driven) | Logging, real-time events | Callbacks fired on each status change |

### When to Use Each

- **DashboardProtocol**: Best for rendering UIs that need complete state snapshots
- **StatusTracker callbacks**: Best for logging, event streaming, or reacting to specific events

## DashboardProtocol

The protocol defines three methods:

```python
from antflow import DashboardProtocol

class MyDashboard:
    def on_start(self, pipeline, total_items):
        """Called when pipeline execution starts."""
        pass

    def on_update(self, snapshot):
        """Called periodically with current pipeline state."""
        pass

    def on_finish(self, results, summary):
        """Called when pipeline execution completes."""
        pass
```

## Simple Example

Here's a minimal custom dashboard that logs to console:

```python
from antflow import Pipeline, Stage

class LoggingDashboard:
    def on_start(self, pipeline, total_items):
        print(f"Starting pipeline with {total_items} items")

    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats
        print(f"Progress: {stats.items_processed}/{stats.items_processed + stats.items_in_flight}")

    def on_finish(self, results, summary):
        print(f"Done! {len(results)} succeeded, {summary.total_failed} failed")

# Use it
pipeline = Pipeline(stages=[...])
results = await pipeline.run(items, custom_dashboard=LoggingDashboard())
```

## Using DashboardSnapshot

The `on_update` method receives a `DashboardSnapshot` with:

- `worker_states`: Dict of worker name to `WorkerState`
- `worker_metrics`: Dict of worker name to `WorkerMetrics`
- `pipeline_stats`: `PipelineStats` object
- `timestamp`: Unix timestamp

```python
def on_update(self, snapshot):
    # Access pipeline statistics
    stats = snapshot.pipeline_stats
    print(f"Processed: {stats.items_processed}")
    print(f"Failed: {stats.items_failed}")
    print(f"In flight: {stats.items_in_flight}")

    # Access per-stage statistics
    for stage_name, stage_stat in stats.stage_stats.items():
        print(f"Stage {stage_name}:")
        print(f"  Pending: {stage_stat.pending_items}")
        print(f"  In progress: {stage_stat.in_progress_items}")
        print(f"  Completed: {stage_stat.completed_items}")

    # Access worker states
    busy_workers = [
        name for name, state in snapshot.worker_states.items()
        if state.status == "busy"
    ]
    print(f"Busy workers: {busy_workers}")

    # Access worker metrics
    for name, metrics in snapshot.worker_metrics.items():
        print(f"{name}: {metrics.items_processed} items, avg {metrics.avg_processing_time:.2f}s")
```

## Using ErrorSummary

The `on_finish` method receives an `ErrorSummary`:

```python
def on_finish(self, results, summary):
    if summary.total_failed > 0:
        print(f"Errors by type:")
        for error_type, count in summary.errors_by_type.items():
            print(f"  {error_type}: {count}")

        print(f"Errors by stage:")
        for stage, count in summary.errors_by_stage.items():
            print(f"  {stage}: {count}")

        print(f"Failed items:")
        for item in summary.failed_items:
            print(f"  ID {item.item_id}: {item.error}")
```

## Subclassing BaseDashboard

For more complex dashboards, subclass `BaseDashboard`:

```python
from antflow.display import BaseDashboard

class MyRichDashboard(BaseDashboard):
    def __init__(self):
        self.total = 0

    def on_start(self, pipeline, total_items):
        self.total = total_items
        print("Starting...")

    def render(self, snapshot):
        # This is called by on_update
        stats = snapshot.pipeline_stats
        pct = (stats.items_processed / self.total * 100) if self.total else 0
        print(f"\rProgress: {pct:.1f}%", end="")

    def on_finish(self, results, summary):
        print(f"\nDone: {len(results)} results")
```

## Integration with Rich

For terminal UIs, use the Rich library:

```python
from rich.console import Console
from rich.live import Live
from rich.table import Table
from antflow.display import BaseDashboard

class RichTableDashboard(BaseDashboard):
    def __init__(self):
        self.console = Console()
        self.live = None
        self.total = 0

    def on_start(self, pipeline, total_items):
        self.total = total_items
        self.live = Live(self._make_table(None), console=self.console)
        self.live.start()

    def render(self, snapshot):
        if self.live:
            self.live.update(self._make_table(snapshot))

    def on_finish(self, results, summary):
        if self.live:
            self.live.stop()
        self.console.print(f"[green]Done![/green] {len(results)} results")

    def _make_table(self, snapshot):
        table = Table(title="Pipeline Status")
        table.add_column("Stage")
        table.add_column("Progress")

        if snapshot:
            for name, stat in snapshot.pipeline_stats.stage_stats.items():
                table.add_row(name, f"{stat.completed_items} done")

        return table
```

## Web Dashboard Integration

AntFlow provides all the data you need to build custom web dashboards. Here's how to integrate with your frontend.

### Available Data

The `DashboardSnapshot` contains everything you need:

```python
snapshot = pipeline.get_dashboard_snapshot()

# Overall stats
snapshot.pipeline_stats.items_processed   # Items completed (all stages)
snapshot.pipeline_stats.items_failed      # Items that failed
snapshot.pipeline_stats.items_in_flight   # Items currently being processed
snapshot.pipeline_stats.queue_sizes       # Dict[stage_name, queue_size]

# Per-stage stats
for stage_name, stage_stat in snapshot.pipeline_stats.stage_stats.items():
    stage_stat.pending_items      # Waiting in queue
    stage_stat.in_progress_items  # Being processed
    stage_stat.completed_items    # Finished this stage
    stage_stat.failed_items       # Failed at this stage

# Worker states
for worker_name, state in snapshot.worker_states.items():
    state.stage            # Which stage this worker belongs to
    state.status           # "idle" or "busy"
    state.current_item_id  # Item being processed (or None)
    state.processing_since # Timestamp when started (or None)

# Worker metrics
for worker_name, metrics in snapshot.worker_metrics.items():
    metrics.items_processed       # Total items processed by this worker
    metrics.items_failed          # Total items failed by this worker
    metrics.avg_processing_time   # Average time per item (seconds)
```

### FastAPI REST Endpoint Example

```python
from fastapi import FastAPI
from antflow import Pipeline, Stage

app = FastAPI()
pipeline = None  # Will be set when pipeline starts

@app.get("/api/pipeline/status")
async def get_status():
    """REST endpoint that returns current pipeline state."""
    if not pipeline:
        return {"status": "not_running"}

    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats

    return {
        "status": "running",
        "progress": {
            "processed": stats.items_processed,
            "failed": stats.items_failed,
            "in_flight": stats.items_in_flight,
            "total": total_items,
        },
        "stages": {
            name: {
                "pending": s.pending_items,
                "active": s.in_progress_items,
                "completed": s.completed_items,
                "failed": s.failed_items,
            }
            for name, s in stats.stage_stats.items()
        },
        "workers": {
            name: {
                "stage": state.stage,
                "status": state.status,
                "current_item": state.current_item_id,
            }
            for name, state in snapshot.worker_states.items()
        }
    }

@app.post("/api/pipeline/start")
async def start_pipeline(items: list):
    """Start pipeline processing."""
    global pipeline, total_items
    total_items = len(items)

    pipeline = Pipeline(stages=[
        Stage("Process", workers=5, tasks=[my_task])
    ])

    # Run in background
    asyncio.create_task(pipeline.run(items))
    return {"status": "started", "total": total_items}
```

### FastAPI WebSocket Example (Real-Time)

```python
from fastapi import FastAPI, WebSocket
from antflow import Pipeline, Stage

app = FastAPI()

@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()

    try:
        while True:
            if pipeline:
                snapshot = pipeline.get_dashboard_snapshot()
                stats = snapshot.pipeline_stats

                await websocket.send_json({
                    "processed": stats.items_processed,
                    "failed": stats.items_failed,
                    "in_flight": stats.items_in_flight,
                    "stages": {
                        name: {
                            "pending": s.pending_items,
                            "active": s.in_progress_items,
                            "completed": s.completed_items,
                        }
                        for name, s in stats.stage_stats.items()
                    }
                })

            await asyncio.sleep(0.1)  # Update rate: 10 Hz
    except Exception:
        pass  # Client disconnected
```

### Using DashboardProtocol with WebSocket

For push-based updates (instead of polling), use `custom_dashboard`:

```python
class WebSocketDashboard:
    def __init__(self, websocket):
        self.ws = websocket

    def on_start(self, pipeline, total_items):
        asyncio.create_task(self.ws.send_json({
            "type": "start",
            "total": total_items,
            "stages": [s.name for s in pipeline.stages]
        }))

    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats
        asyncio.create_task(self.ws.send_json({
            "type": "update",
            "processed": stats.items_processed,
            "failed": stats.items_failed,
            "in_flight": stats.items_in_flight,
            "stages": {
                name: {"pending": s.pending_items, "active": s.in_progress_items, "done": s.completed_items}
                for name, s in stats.stage_stats.items()
            }
        }))

    def on_finish(self, results, summary):
        asyncio.create_task(self.ws.send_json({
            "type": "finish",
            "results": len(results),
            "failed": summary.total_failed,
            "errors": summary.errors_by_type
        }))

# Usage with FastAPI
@app.websocket("/ws/pipeline/run")
async def run_with_websocket(websocket: WebSocket, items: list):
    await websocket.accept()

    pipeline = Pipeline(stages=[...])
    dashboard = WebSocketDashboard(websocket)

    results = await pipeline.run(items, custom_dashboard=dashboard)
    # Dashboard automatically sends start, updates, and finish events
```

### Frontend JavaScript Example

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/pipeline');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // Update progress bar
    const pct = (data.processed / totalItems) * 100;
    document.getElementById('progress').style.width = `${pct}%`;

    // Update stage table
    for (const [stage, stats] of Object.entries(data.stages)) {
        document.getElementById(`stage-${stage}-pending`).textContent = stats.pending;
        document.getElementById(`stage-${stage}-active`).textContent = stats.active;
        document.getElementById(`stage-${stage}-done`).textContent = stats.done;
    }

    // Update counters
    document.getElementById('processed').textContent = data.processed;
    document.getElementById('failed').textContent = data.failed;
};
```

### Flask Example (Synchronous)

```python
from flask import Flask, jsonify
import asyncio
from antflow import Pipeline, Stage

app = Flask(__name__)
pipeline = None
loop = asyncio.new_event_loop()

@app.route('/api/status')
def get_status():
    if not pipeline:
        return jsonify({"status": "not_running"})

    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats

    return jsonify({
        "processed": stats.items_processed,
        "failed": stats.items_failed,
        "stages": {
            name: {"done": s.completed_items, "active": s.in_progress_items}
            for name, s in stats.stage_stats.items()
        }
    })
```

## Multi-Stage Progress Visualization

When running pipelines with multiple stages, understanding progress requires per-stage visibility.

### The Problem

The `items_processed` counter only increments when items **complete all stages**:

```
Pipeline: Fetch → Process → Save
Items:    100       50        10

items_processed = 10  (only counts items that finished ALL stages)
```

### Solution: Use stage_stats

The `DashboardSnapshot` provides `stage_stats` for per-stage visibility:

```python
class MultiStageDashboard:
    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats

        print(f"Overall: {stats.items_processed}/{self.total} completed end-to-end")
        print()

        # Per-stage breakdown
        for stage_name, stage_stat in stats.stage_stats.items():
            total_in_stage = (
                stage_stat.pending_items +
                stage_stat.in_progress_items +
                stage_stat.completed_items +
                stage_stat.failed_items
            )
            print(f"{stage_name}:")
            print(f"  Pending:     {stage_stat.pending_items}")
            print(f"  In Progress: {stage_stat.in_progress_items}")
            print(f"  Completed:   {stage_stat.completed_items}")
            print(f"  Failed:      {stage_stat.failed_items}")
```

### Visual Example

```
╭─────────────────────── Multi-Stage Pipeline ───────────────────────╮
│                                                                     │
│  Overall: [██░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 10% (10/100 end-to-end) │
│                                                                     │
│  Stage      │ Pending │ In Progress │ Completed │ Failed           │
│  ───────────┼─────────┼─────────────┼───────────┼──────            │
│  Fetch      │    0    │      3      │    97     │   0              │
│  Process    │   47    │      5      │    45     │   0              │
│  Save       │   35    │      2      │    10     │   0              │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯
```

## Alternative: StatusTracker Callbacks (Event-Driven)

For event-driven monitoring (instead of polling), use `StatusTracker` callbacks:

```python
from antflow import Pipeline, Stage, StatusTracker, StatusEvent

async def on_status_change(event: StatusEvent):
    """Called on EVERY status change (queued, in_progress, completed, failed)."""
    print(f"[{event.timestamp}] Item {event.item_id}: {event.status} @ {event.stage}")

async def main():
    tracker = StatusTracker(on_status_change=on_status_change)

    pipeline = Pipeline(
        stages=[
            Stage("Fetch", workers=3, tasks=[fetch]),
            Stage("Process", workers=5, tasks=[process]),
        ],
        tracker=tracker,
    )

    results = await pipeline.run(items)  # Callbacks fire during execution
```

### Task-Level Callbacks

For even finer granularity, use task-level callbacks:

```python
tracker = StatusTracker(
    on_status_change=handle_item_status,    # Item-level events
    on_task_start=handle_task_start,        # Task started
    on_task_complete=handle_task_complete,  # Task succeeded
    on_task_retry=handle_task_retry,        # Task being retried
    on_task_fail=handle_task_fail,          # Task failed
)
```

## Combining Both Approaches

You can use both DashboardProtocol AND StatusTracker together:

```python
async def log_failures(event: StatusEvent):
    if event.status == "failed":
        logging.error(f"Item {event.item_id} failed at {event.stage}: {event.metadata}")

tracker = StatusTracker(on_status_change=log_failures)

pipeline = Pipeline(stages=[...], tracker=tracker)

# Dashboard for UI + callbacks for logging
results = await pipeline.run(items, dashboard="compact")
```

## Manual Polling (Without DashboardProtocol)

If you prefer complete control, you can poll manually:

```python
import asyncio
from antflow import Pipeline, Stage

async def main():
    pipeline = Pipeline(stages=[...])

    # Start pipeline in background
    await pipeline.start()
    await pipeline.feed(items)

    # Manual polling loop
    while True:
        snapshot = pipeline.get_dashboard_snapshot()
        stats = snapshot.pipeline_stats

        print(f"\rProcessed: {stats.items_processed}", end="")

        if stats.items_processed + stats.items_failed >= len(items):
            break

        await asyncio.sleep(0.1)

    await pipeline.join()
    results = pipeline.results
```

This gives you full control over when and how to query pipeline state.
