"""
Real-time dashboard example with WebSocket streaming.

This example demonstrates how to build a real-time dashboard
that monitors pipeline execution via WebSocket.
"""

import asyncio
import json
from typing import Set

from antflow import Pipeline, PipelineDashboard, Stage, StatusEvent, StatusTracker


async def process_item(x: int) -> int:
    """Simulate some processing work."""
    await asyncio.sleep(0.1)
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
        print(f"[WS-{self.client_id}] Sent: {json.dumps(data, indent=2)}")


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
        print(f"\n[Server] Client {websocket.client_id} connected")

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

        print(f"[Server] Client {websocket.client_id} subscribed to events")

    async def disconnect_client(self, websocket: MockWebSocket):
        """Handle client disconnection."""
        self.clients.discard(websocket)
        print(f"[Server] Client {websocket.client_id} disconnected")


async def print_dashboard_updates(snapshot):
    """Print dashboard updates to console."""
    active_workers = [
        name for name, state in snapshot.worker_states.items()
        if state.status == "busy"
    ]

    print(f"\n{'='*60}")
    print(f"Dashboard Update @ {snapshot.timestamp:.2f}")
    print(f"{'='*60}")
    print(f"Active workers: {len(active_workers)}/{len(snapshot.worker_states)}")
    print(f"Items processed: {snapshot.pipeline_stats.items_processed}")
    print(f"Items failed: {snapshot.pipeline_stats.items_failed}")
    print(f"Items in flight: {snapshot.pipeline_stats.items_in_flight}")
    print(f"Queue sizes: {snapshot.pipeline_stats.queue_sizes}")

    if active_workers:
        print(f"\nBusy workers:")
        for worker in active_workers[:5]:
            state = snapshot.worker_states[worker]
            print(f"  - {worker}: processing item {state.current_item_id}")

    top_performers = sorted(
        snapshot.worker_metrics.items(),
        key=lambda x: x[1].items_processed,
        reverse=True
    )[:3]

    if top_performers:
        print(f"\nTop performers:")
        for worker, metrics in top_performers:
            if metrics.items_processed > 0:
                print(
                    f"  - {worker}: {metrics.items_processed} items, "
                    f"avg {metrics.avg_processing_time:.3f}s"
                )


async def main():
    print("=== Real-Time Dashboard with WebSocket Example ===\n")

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

    dashboard = PipelineDashboard(
        pipeline=pipeline,
        tracker=tracker,
        on_update=print_dashboard_updates,
        update_interval=2.0
    )

    server = DashboardServer(dashboard)

    client1 = MockWebSocket("client-1")
    client2 = MockWebSocket("client-2")

    await server.handle_client(client1)
    await server.handle_client(client2)

    async with dashboard:
        print("\n[Pipeline] Starting processing of 50 items...\n")

        pipeline_task = asyncio.create_task(pipeline.run(range(50)))

        await pipeline_task

        await asyncio.sleep(1.0)

    await server.disconnect_client(client1)
    await server.disconnect_client(client2)

    print(f"\n{'='*60}")
    print("Final Statistics")
    print(f"{'='*60}")

    final_snapshot = dashboard.get_snapshot()

    print(f"Total processed: {final_snapshot.pipeline_stats.items_processed}")
    print(f"Total failed: {final_snapshot.pipeline_stats.items_failed}")

    print(f"\nWorker metrics:")
    for worker, metrics in sorted(dashboard.get_worker_metrics().items()):
        if metrics.items_processed > 0 or metrics.items_failed > 0:
            print(
                f"  {worker}: "
                f"{metrics.items_processed} processed, "
                f"{metrics.items_failed} failed, "
                f"avg {metrics.avg_processing_time:.3f}s"
            )

    utilization = dashboard.get_worker_utilization()
    avg_utilization = sum(utilization.values()) / len(utilization) if utilization else 0
    print(f"\nAverage worker utilization: {avg_utilization*100:.1f}%")

    print(f"\nClient 1 received {len(client1.messages)} messages")
    print(f"Client 2 received {len(client2.messages)} messages")


if __name__ == "__main__":
    asyncio.run(main())
