# Display Module API

The `antflow.display` module provides progress bars and dashboards for pipeline monitoring.

## ProgressDisplay

Minimal terminal progress bar without external dependencies.

```python
from antflow.display import ProgressDisplay
```

### Constructor

```python
ProgressDisplay(
    total: int,
    width: int = 30,
    fill_char: str = "█",
    empty_char: str = "░",
)
```

**Parameters:**

- `total`: Total number of items to process
- `width`: Width of the progress bar in characters
- `fill_char`: Character for completed portion
- `empty_char`: Character for remaining portion

### Methods

- `on_start(pipeline, total_items)`: Initialize progress tracking
- `on_update(snapshot)`: Update display with current state
- `on_finish(results, summary)`: Show completion message

### Usage

```python
# Automatic via pipeline
results = await pipeline.run(items, progress=True)

# Manual usage
progress = ProgressDisplay(total=100)
progress.on_start(pipeline, 100)
# ... during processing ...
progress.on_update(snapshot)
progress.on_finish(results, summary)
```

---

## BaseDashboard

Abstract base class for custom dashboards.

```python
from antflow.display import BaseDashboard
```

### Methods

- `on_start(pipeline, total_items)`: Called when pipeline starts
- `on_update(snapshot)`: Called periodically (calls `render()`)
- `on_finish(results, summary)`: Called when pipeline completes
- `render(snapshot)`: Abstract method - implement display logic

### Example

```python
class MyDashboard(BaseDashboard):
    def render(self, snapshot):
        stats = snapshot.pipeline_stats
        print(f"Progress: {stats.items_processed}")
```

---

## CompactDashboard

Rich-based compact dashboard showing essential metrics.

```python
from antflow.display import CompactDashboard
```

### Constructor

```python
CompactDashboard(refresh_rate: float = 4.0)
```

**Parameters:**

- `refresh_rate`: Display refresh rate in Hz

### Display

Shows a single panel with:

- Progress bar with percentage
- Current stage activity
- Processing rate and ETA
- Success/failure counts

### Usage

```python
results = await pipeline.run(items, dashboard="compact")
```

---

## DetailedDashboard

Rich-based dashboard with stage-level metrics.

```python
from antflow.display import DetailedDashboard
```

### Constructor

```python
DetailedDashboard(refresh_rate: float = 4.0)
```

### Display

Shows:

- Overall progress bar with rate and ETA
- Per-stage table with worker counts
- Worker performance metrics table

### Usage

```python
results = await pipeline.run(items, dashboard="detailed")
```

---

## FullDashboard

Rich-based comprehensive dashboard with full monitoring.

```python
from antflow.display import FullDashboard
```

### Constructor

```python
FullDashboard(
    refresh_rate: float = 4.0,
    max_items_shown: int = 20,
)
```

**Parameters:**

- `refresh_rate`: Display refresh rate in Hz
- `max_items_shown`: Maximum items to show in item tracker

### Display

Shows:

- Overview panel with statistics
- Stage metrics table
- Worker monitoring table
- Item tracking table (requires `StatusTracker`)

### Usage

```python
tracker = StatusTracker()
pipeline = Pipeline(stages=[...], status_tracker=tracker)
results = await pipeline.run(items, dashboard="full")
```

---

## DashboardProtocol

Protocol for custom dashboard implementations.

```python
from antflow import DashboardProtocol
```

### Methods

```python
def on_start(self, pipeline: Pipeline, total_items: int) -> None:
    """Called when pipeline execution starts."""
    ...

def on_update(self, snapshot: DashboardSnapshot) -> None:
    """Called periodically with current pipeline state."""
    ...

def on_finish(
    self,
    results: List[PipelineResult],
    summary: ErrorSummary
) -> None:
    """Called when pipeline execution completes."""
    ...
```

### Usage

```python
class MyDashboard:
    def on_start(self, pipeline, total_items):
        print(f"Starting {total_items} items")

    def on_update(self, snapshot):
        print(f"Processed: {snapshot.pipeline_stats.items_processed}")

    def on_finish(self, results, summary):
        print(f"Done: {len(results)} results")

results = await pipeline.run(items, custom_dashboard=MyDashboard())
```

---

## Types

### DashboardSnapshot

```python
@dataclass
class DashboardSnapshot:
    worker_states: Dict[str, WorkerState]
    worker_metrics: Dict[str, WorkerMetrics]
    pipeline_stats: PipelineStats
    timestamp: float
```

### ErrorSummary

```python
@dataclass
class ErrorSummary:
    total_failed: int
    errors_by_type: Dict[str, int]
    errors_by_stage: Dict[str, int]
    failed_items: List[FailedItem]
```

### FailedItem

```python
@dataclass
class FailedItem:
    item_id: Any
    error: str
    error_type: str
    stage: str
    attempts: int
    timestamp: float
```
