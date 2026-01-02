# AntFlow Web Dashboard Example

A complete web dashboard example using FastAPI and WebSocket for real-time pipeline monitoring.

## Features

- **Real-time updates** via WebSocket (10 Hz)
- **REST API** for status polling
- **Multi-stage visualization** with progress bars
- **Worker monitoring** with status indicators
- **Start/Stop controls** from the web UI

## Screenshot

```
╭─────────────────────────────────────────────────────────────╮
│  ⚡ AntFlow Dashboard                          [Running]    │
├─────────────────────────────────────────────────────────────┤
│  Overall Progress                                           │
│  [████████████████░░░░░░░░░░░░░░] 52.0%                    │
│                                                             │
│  Processed: 47    Failed: 5    In Flight: 12   Remaining: 48│
├─────────────────────────────────────────────────────────────┤
│  Stage     │ Pending │ Active │ Done │ Failed │ Progress   │
│  ──────────┼─────────┼────────┼──────┼────────┼───────────│
│  Fetch     │    8    │   5    │  87  │   0    │ [████████] │
│  Process   │   35    │   3    │  54  │   2    │ [█████░░░] │
│  Save      │   20    │   2    │  30  │   3    │ [███░░░░░] │
╰─────────────────────────────────────────────────────────────╯
```

## Requirements

```bash
pip install fastapi uvicorn
```

## Running

```bash
# From the web_dashboard directory
cd examples/web_dashboard

# Start the server
python server.py
# or
uvicorn server:app --reload

# Open in browser
open http://localhost:8000
```

## API Endpoints

### REST

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Get current pipeline status |
| POST | `/api/start?num_items=100` | Start pipeline with N items |
| POST | `/api/stop` | Stop pipeline gracefully |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws` | Real-time status updates (JSON) |

## Response Format

```json
{
  "is_running": true,
  "progress": {
    "processed": 47,
    "failed": 5,
    "in_flight": 12,
    "total": 100
  },
  "stages": {
    "Fetch": {"pending": 8, "active": 5, "completed": 87, "failed": 0},
    "Process": {"pending": 35, "active": 3, "completed": 54, "failed": 2},
    "Save": {"pending": 20, "active": 2, "completed": 30, "failed": 3}
  },
  "workers": [
    {"name": "Fetch-W0", "stage": "Fetch", "status": "busy", "current_item": 42},
    {"name": "Fetch-W1", "stage": "Fetch", "status": "idle", "current_item": null}
  ]
}
```

## Customization

### Change Pipeline Tasks

Edit `server.py` and modify the task functions:

```python
async def my_custom_task(x: int) -> dict:
    # Your processing logic here
    result = await call_external_api(x)
    return result
```

### Change Pipeline Structure

```python
pipeline = Pipeline(
    stages=[
        Stage("Extract", workers=10, tasks=[extract_task]),
        Stage("Transform", workers=5, tasks=[transform_task]),
        Stage("Load", workers=3, tasks=[load_task]),
    ]
)
```

### Change Update Rate

In `server.py`, modify the sleep interval in `status_broadcaster()`:

```python
await asyncio.sleep(0.1)  # 10 Hz (default)
await asyncio.sleep(0.5)  # 2 Hz (lower CPU usage)
await asyncio.sleep(0.05) # 20 Hz (smoother updates)
```

## Integration with Your App

### As a Standalone Service

Run the dashboard as a separate service and integrate via API:

```python
import httpx

async def check_pipeline_status():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/status")
        return response.json()
```

### Embedded in Your FastAPI App

```python
from fastapi import FastAPI
from antflow import Pipeline, Stage

app = FastAPI()

@app.get("/my-pipeline/status")
async def get_my_pipeline_status():
    snapshot = my_pipeline.get_dashboard_snapshot()
    return {
        "processed": snapshot.pipeline_stats.items_processed,
        "stages": {
            name: s.completed_items
            for name, s in snapshot.pipeline_stats.stage_stats.items()
        }
    }
```

## Architecture

```
┌─────────────┐     WebSocket      ┌─────────────┐
│   Browser   │◄──────────────────►│   FastAPI   │
│  (index.html│     /ws            │  (server.py)│
└─────────────┘                    └──────┬──────┘
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │   AntFlow   │
                                   │  Pipeline   │
                                   └─────────────┘
```

The dashboard queries `pipeline.get_dashboard_snapshot()` every 100ms and broadcasts updates to all connected WebSocket clients.
