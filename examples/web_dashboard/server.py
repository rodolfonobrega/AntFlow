"""
FastAPI Web Dashboard for AntFlow pipelines.

Run with: uvicorn server:app --reload
Open: http://localhost:8000

This example demonstrates:
- REST endpoint to get pipeline status
- WebSocket for real-time updates
- Starting/stopping pipeline from web UI
"""

import asyncio
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from antflow import Pipeline, Stage


pipeline: Optional[Pipeline] = None
total_items: int = 0
is_running: bool = False
connected_clients: set[WebSocket] = set()


async def fetch_data(x: int) -> dict:
    """Simulate fetching data from an API."""
    await asyncio.sleep(random.uniform(0.1, 0.3))
    if random.random() < 0.05:
        raise ConnectionError(f"Failed to fetch item {x}")
    return {"id": x, "data": f"fetched_{x}"}


async def process_data(data: dict) -> dict:
    """Simulate processing data."""
    await asyncio.sleep(random.uniform(0.05, 0.2))
    if random.random() < 0.03:
        raise ValueError(f"Invalid data for item {data['id']}")
    data["processed"] = True
    return data


async def save_data(data: dict) -> dict:
    """Simulate saving data to database."""
    await asyncio.sleep(random.uniform(0.05, 0.15))
    data["saved"] = True
    return data


async def broadcast_status():
    """Broadcast pipeline status to all connected WebSocket clients."""
    if not pipeline or not connected_clients:
        return

    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats

    message = {
        "type": "update",
        "is_running": is_running,
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
        "workers": [
            {
                "name": name,
                "stage": state.stage,
                "status": state.status,
                "current_item": state.current_item_id,
            }
            for name, state in sorted(snapshot.worker_states.items())
        ],
    }

    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.add(client)

    connected_clients.difference_update(disconnected)


async def status_broadcaster():
    """Background task to broadcast status updates."""
    while True:
        await broadcast_status()
        await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background broadcaster on startup."""
    task = asyncio.create_task(status_broadcaster())
    yield
    task.cancel()


app = FastAPI(title="AntFlow Web Dashboard", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML page."""
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/api/status")
async def get_status():
    """REST endpoint: Get current pipeline status."""
    if not pipeline:
        return {
            "is_running": False,
            "progress": {"processed": 0, "failed": 0, "in_flight": 0, "total": 0},
            "stages": {},
            "workers": [],
        }

    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats

    return {
        "is_running": is_running,
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
        "workers": [
            {
                "name": name,
                "stage": state.stage,
                "status": state.status,
                "current_item": state.current_item_id,
            }
            for name, state in sorted(snapshot.worker_states.items())
        ],
    }


@app.post("/api/start")
async def start_pipeline(num_items: int = 100):
    """Start pipeline processing."""
    global pipeline, total_items, is_running

    if is_running:
        return {"error": "Pipeline already running"}

    total_items = num_items
    is_running = True

    pipeline = Pipeline(
        stages=[
            Stage("Fetch", workers=5, tasks=[fetch_data], task_attempts=3),
            Stage("Process", workers=3, tasks=[process_data], task_attempts=2),
            Stage("Save", workers=2, tasks=[save_data], task_attempts=2),
        ]
    )

    async def run_pipeline():
        global is_running
        try:
            items = list(range(num_items))
            await pipeline.run(items)
        finally:
            is_running = False
            await broadcast_status()

    asyncio.create_task(run_pipeline())

    return {"status": "started", "total": num_items}


@app.post("/api/stop")
async def stop_pipeline():
    """Stop pipeline (graceful shutdown)."""
    global is_running

    if not is_running:
        return {"error": "Pipeline not running"}

    is_running = False
    return {"status": "stopping"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    connected_clients.add(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
