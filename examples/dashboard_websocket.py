"""
WebSocket integration pattern example.

Demonstrates how to integrate AntFlow with a WebSocket server for real-time
browser-based dashboards. This example uses mock WebSockets to show the pattern.

Key concepts:
- PipelineDashboard.subscribe(): Register callbacks for status changes
- PipelineDashboard.get_snapshot(): Get complete pipeline state
- DashboardServer pattern: Manage multiple WebSocket clients
- Event forwarding: Stream status changes to connected clients

To use with a real WebSocket framework (e.g., FastAPI):
1. Replace MockWebSocket with FastAPI's WebSocket
2. Create an endpoint that calls server.handle_client(websocket)
3. The rest of the pattern remains the same

Example FastAPI integration:
    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        await websocket.accept()
        await server.handle_client(websocket)
"""

import asyncio
import random
import time
from collections import deque
from typing import Deque, Set

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from antflow import Pipeline, PipelineDashboard, Stage, StatusEvent, StatusTracker

# Global log buffer
log_messages: Deque[str] = deque(maxlen=20)

def log(message: str):
    """Log a message to the buffer."""
    timestamp = time.strftime("%H:%M:%S")
    log_messages.append(f"[{timestamp}] {message}")

async def process_item(x: int) -> int:
    """Simulate some processing work."""
    await asyncio.sleep(random.uniform(0.1, 0.5))
    if x % 10 == 0:
        raise ValueError(f"Item {x} failed processing")
    return x * 2


class MockWebSocket:
    """Mock WebSocket for demonstration (replace with real FastAPI WebSocket)."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.messages = []

    async def send_json(self, data: dict):
        """Simulate sending JSON to client."""
        self.messages.append(data)
        # Log only significant events to avoid flooding the log panel
        if data.get("type") == "initial_state":
            log(f"[WS-{self.client_id}] Sent initial state")
        elif data.get("type") == "status_change":
            event = data.get("event", {})
            if event.get("status") == "failed":
                 log(f"[WS-{self.client_id}] Sent failure alert for item {event.get('item_id')}")


class DashboardServer:
    """Dashboard server managing WebSocket connections."""

    def __init__(self, dashboard: PipelineDashboard):
        self.dashboard = dashboard
        self.clients: Set[MockWebSocket] = set()

    async def broadcast(self, data: dict):
        """Broadcast message to all connected clients."""
        for client in self.clients:
            await client.send_json(data)

    async def handle_client(self, websocket: MockWebSocket):
        """Handle a WebSocket client connection."""
        self.clients.add(websocket)
        log(f"[Server] Client {websocket.client_id} connected")

        initial_snapshot = self.dashboard.get_snapshot()
        await websocket.send_json({
            "type": "initial_state",
            "snapshot": {
                "workers": {
                    name: {
                        "status": state.status,
                        "current_item": state.current_item_id,
                        "processing_since": state.processing_since
                    }
                    for name, state in initial_snapshot.worker_states.items()
                },
                "metrics": {
                    name: {
                        "items_processed": metric.items_processed,
                        "items_failed": metric.items_failed,
                        "avg_time": metric.avg_processing_time
                    }
                    for name, metric in initial_snapshot.worker_metrics.items()
                },
                "stats": {
                    "items_processed": initial_snapshot.pipeline_stats.items_processed,
                    "items_failed": initial_snapshot.pipeline_stats.items_failed,
                    "items_in_flight": initial_snapshot.pipeline_stats.items_in_flight,
                    "queue_sizes": initial_snapshot.pipeline_stats.queue_sizes
                }
            }
        })

        async def on_status_change(event: StatusEvent):
            """Forward status changes to client."""
            await websocket.send_json({
                "type": "status_change",
                "event": {
                    "item_id": event.item_id,
                    "stage": event.stage,
                    "status": event.status,
                    "worker": event.worker,
                    "timestamp": event.timestamp,
                    "metadata": event.metadata
                }
            })

        self.dashboard.subscribe(on_status_change)

        log(f"[Server] Client {websocket.client_id} subscribed to events")

    async def disconnect_client(self, websocket: MockWebSocket):
        """Handle client disconnection."""
        self.clients.discard(websocket)
        log(f"[Server] Client {websocket.client_id} disconnected")


def generate_dashboard(pipeline: Pipeline, tracker: StatusTracker, total_items: int) -> Layout:
    """Generate the dashboard layout."""
    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats

    # Main Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="upper", size=12),
        Layout(name="logs", ratio=1)
    )

    # Header
    layout["header"].update(
        Panel(
            Text("AntFlow WebSocket Dashboard", justify="center", style="bold cyan"),
            style="cyan"
        )
    )

    # Upper Section - Split into Stats and Workers
    layout["upper"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="workers", ratio=2)
    )

    # Stats Table
    stats_table = Table(title="Pipeline Statistics", expand=True)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="magenta")

    stats_table.add_row("Total Items", str(total_items))
    stats_table.add_row("Processed", str(stats.items_processed))
    stats_table.add_row("Failed", str(stats.items_failed))
    stats_table.add_row("In Flight", str(stats.items_in_flight))

    # Calculate progress
    completed_count = stats.items_processed + stats.items_failed
    progress_pct = (completed_count / total_items) * 100 if total_items > 0 else 0
    stats_table.add_row("Progress", f"{progress_pct:.1f}%")

    layout["stats"].update(Panel(stats_table, title="Overview"))

    # Worker Monitor Table
    worker_table = Table(title="Worker Monitor", expand=True)
    worker_table.add_column("Worker", style="blue")
    worker_table.add_column("Stage", style="yellow")
    worker_table.add_column("Status", style="white")
    worker_table.add_column("Current Item", style="cyan")
    worker_table.add_column("Processed", style="green", justify="right")

    for worker_name, state in sorted(snapshot.worker_states.items()):
        metrics = snapshot.worker_metrics.get(worker_name)
        processed = metrics.items_processed if metrics else 0

        status_style = "bold green" if state.status == "busy" else "dim white"
        current_item = str(state.current_item_id) if state.current_item_id is not None else "-"

        worker_table.add_row(
            worker_name,
            state.stage,
            Text(state.status.upper(), style=status_style),
            current_item,
            str(processed)
        )

    layout["workers"].update(Panel(worker_table, title="Active Workers"))

    # Logs Panel
    log_text = Text()
    for msg in log_messages:
        log_text.append(msg + "\n")

    layout["logs"].update(Panel(log_text, title="Server Logs", style="white"))

    return layout


async def main():
    console = Console()

    tracker = StatusTracker()

    stage1 = Stage(
        name="Fetch",
        workers=3,
        tasks=[process_item],
        retry="per_task",
        task_attempts=2
    )

    stage2 = Stage(
        name="Process",
        workers=2,
        tasks=[process_item],
        retry="per_task",
        task_attempts=1
    )

    pipeline = Pipeline(
        stages=[stage1, stage2],
        status_tracker=tracker
    )

    # We don't need the Dashboard class for the UI, but we use it for the Server logic
    # Actually, we can just use the pipeline and tracker directly for the UI
    # and keep the server logic separate.

    # Initialize Dashboard for Server (logic only)
    dashboard_logic = PipelineDashboard(
        pipeline=pipeline,
        tracker=tracker,
        update_interval=2.0
    )

    server = DashboardServer(dashboard_logic)

    client1 = MockWebSocket("client-1")
    client2 = MockWebSocket("client-2")

    await server.handle_client(client1)
    await server.handle_client(client2)

    num_items = 50
    items = range(num_items)

    log("Starting pipeline processing...")

    pipeline_task = asyncio.create_task(pipeline.run(items))

    # Live Dashboard Loop
    try:
        with Live(generate_dashboard(pipeline, tracker, num_items), refresh_per_second=4, screen=True) as live:
            while not pipeline_task.done():
                live.update(generate_dashboard(pipeline, tracker, num_items))
                await asyncio.sleep(0.2)

            # Final update
            live.update(generate_dashboard(pipeline, tracker, num_items))
            await asyncio.sleep(2)

    except Exception as e:
        console.print(f"[red]Dashboard Error: {e}[/red]")

    await server.disconnect_client(client1)
    await server.disconnect_client(client2)

    # Final stats
    console.print("\n[bold green]Processing Complete![/bold green]")
    stats = tracker.get_stats()
    console.print(f"Total processed: {stats['completed']}")
    console.print(f"Total failed: {stats['failed']}")

    console.print(f"\nClient 1 received {len(client1.messages)} messages")
    console.print(f"Client 2 received {len(client2.messages)} messages")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
