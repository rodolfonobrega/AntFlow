# Progress Bar Guide

AntFlow provides built-in progress visualization options that require zero configuration.

## Quick Start

The simplest way to add progress visualization is with the `progress=True` flag:

```python
results = await pipeline.run(items, progress=True)
```

This displays a minimal progress bar in your terminal:

```
[████████████░░░░░░░░░░░░░░░░░░] 42% | 126/300 | 24.5/s | 2 failed
```

## Dashboard Options

For more detailed monitoring, use the `dashboard` parameter:

```python
# Compact dashboard - essential metrics only
results = await pipeline.run(items, dashboard="compact")

# Detailed dashboard - per-stage metrics and worker counts
results = await pipeline.run(items, dashboard="detailed")

# Full dashboard - complete monitoring with item tracking
results = await pipeline.run(items, dashboard="full")
```

### Compact Dashboard

Shows a single panel with:

- Progress bar
- Current stage activity
- Processing rate and ETA
- Success/failure counts

```
╭───────────────── AntFlow Pipeline ─────────────────╮
│  [████████████░░░░░░░░░░░░░░░░░░] 42%              │
│  Stage: Process (3/5 workers busy)                 │
│  Rate: 24.5 items/sec | ETA: 00:02:15              │
│  OK: 126 | Failed: 2 | Remaining: 172              │
╰────────────────────────────────────────────────────╯
```

### Detailed Dashboard

Shows:

- Overall progress bar with rate and ETA
- Per-stage progress table with worker counts
- Worker performance metrics

### Full Dashboard

The most comprehensive option, showing:

- Overview statistics
- Stage metrics
- Individual worker monitoring
- Item tracking (requires `StatusTracker`)

For item tracking, add a `StatusTracker`:

```python
from antflow import Pipeline, Stage, StatusTracker

tracker = StatusTracker()
pipeline = Pipeline(stages=[...], status_tracker=tracker)
results = await pipeline.run(items, dashboard="full")
```

## Using with Pipeline.quick()

Progress works with all Pipeline APIs:

```python
# With quick()
results = await Pipeline.quick(items, process, workers=10, progress=True)

# With dashboard
results = await Pipeline.quick(
    items,
    [fetch, process, save],
    workers=5,
    dashboard="compact"
)
```

## Using with Builder API

```python
results = await (
    Pipeline.create()
    .add("Fetch", fetch, workers=10)
    .add("Process", process, workers=5)
    .run(items, dashboard="detailed")
)
```

## Note on Mutual Exclusion

You cannot use both `progress=True` and `dashboard` at the same time:

```python
# This will raise ValueError
results = await pipeline.run(items, progress=True, dashboard="compact")
```

Choose one or the other based on your needs.
