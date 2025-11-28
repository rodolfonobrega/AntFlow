import asyncio
import random
from dataclasses import dataclass, field
from typing import Dict, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from antflow import Pipeline, Stage, StatusEvent, StatusTracker

# Initialize Rich Console
console = Console()

@dataclass
class WorkerState:
    name: str
    stage: str
    status: str = "IDLE"
    current_item: Optional[int] = None
    processed_count: int = 0

# Global state for workers (in a real app, this would be in a class)
worker_states: Dict[str, WorkerState] = {}

async def fetch_data(item_id: int):
    """Simulate fetching data."""
    delay = random.uniform(0.5, 2.0)
    await asyncio.sleep(delay)
    return f"data_{item_id}"

async def process_data(data: str):
    """Simulate processing data."""
    delay = random.uniform(1.0, 3.0)
    await asyncio.sleep(delay)
    if random.random() < 0.1:
        raise ValueError("Processing error")
    return data.upper()

async def save_data(data: str):
    """Simulate saving data."""
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)
    return f"saved_{data}"

def update_worker_state(event: StatusEvent):
    """Update local worker state based on event."""
    if not event.worker:
        return

    worker_name = event.worker
    
    # Initialize if new
    if worker_name not in worker_states:
        worker_states[worker_name] = WorkerState(
            name=worker_name,
            stage=event.stage or "?"
        )
    
    state = worker_states[worker_name]
    
    if event.status == "in_progress":
        state.status = "BUSY"
        state.current_item = event.item_id
    elif event.status in ("completed", "failed"):
        state.status = "IDLE"
        state.current_item = None
        state.processed_count += 1

def generate_layout(pipeline: Pipeline, tracker: StatusTracker, total_items: int) -> Layout:
    """Generate the dashboard layout."""
    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats
    
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="upper", size=16),
        Layout(name="lower")
    )
    
    layout["header"].update(
        Panel(Text("AntFlow Callback Dashboard (With Workers)", justify="center", style="bold green"), style="green")
    )
    
    # Upper Section - Split into Stats and Workers
    layout["upper"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="workers", ratio=2)
    )
    
    # Stats Table
    stats_table = Table(title="Statistics", expand=True)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="magenta")
    
    stats_table.add_row("Total Items", str(total_items))
    stats_table.add_row("Processed", str(stats.items_processed))
    stats_table.add_row("Failed", str(stats.items_failed))
    stats_table.add_row("In Flight", str(stats.items_in_flight))
    
    # Progress
    total_ops = total_items * len(pipeline.stages)
    completed_ops = stats.items_processed + stats.items_failed
    progress_pct = (completed_ops / total_ops) * 100 if total_ops > 0 else 0
    stats_table.add_row("Progress", f"{progress_pct:.1f}%")
    
    layout["stats"].update(Panel(stats_table, title="Overview"))
    
    # Worker Monitor Table (Populated from local state)
    worker_table = Table(title="Worker Monitor", expand=True)
    worker_table.add_column("Worker", style="blue")
    worker_table.add_column("Stage", style="yellow")
    worker_table.add_column("Status", style="white")
    worker_table.add_column("Current Item", style="cyan")
    worker_table.add_column("Processed", style="green", justify="right")
    
    for name, state in sorted(worker_states.items()):
        status_style = "bold green" if state.status == "BUSY" else "dim white"
        current = str(state.current_item) if state.current_item is not None else "-"
        
        worker_table.add_row(
            name,
            state.stage,
            Text(state.status, style=status_style),
            current,
            str(state.processed_count)
        )
        
    layout["workers"].update(Panel(worker_table, title="Active Workers"))
    
    # Items Table
    items_table = Table(title="Recent Activity", expand=True)
    items_table.add_column("ID", style="cyan")
    items_table.add_column("Status", style="white")
    items_table.add_column("Stage", style="blue")
    items_table.add_column("Info", style="dim white")
    
    # Show last 15 items
    start_idx = max(0, total_items - 15)
    for i in range(start_idx, total_items):
        status_event = tracker.get_status(i)
        if status_event:
            status = status_event.status
            info = ""
            
            if status == "completed":
                style = "green"
            elif status == "failed":
                style = "red"
                info = str(status_event.metadata.get("error", ""))
            elif status == "in_progress":
                style = "bold yellow"
            elif status == "retrying":
                style = "bold magenta"
                attempt = status_event.metadata.get("attempt", 1)
                status = f"RETRYING ({attempt-1})"
                info = str(status_event.metadata.get("error", ""))
            else:
                style = "white"
                
            items_table.add_row(str(i), Text(status.upper(), style=style), status_event.stage or "-", info)
            
    layout["lower"].update(Panel(items_table, title="Items"))
    
    return layout

async def main():
    # 1. Setup
    num_items = 50
    tracker = StatusTracker()
    
    stage1 = Stage(name="Fetch", workers=4, tasks=[fetch_data])
    stage2 = Stage(name="Process", workers=3, tasks=[process_data], retry="per_stage", stage_attempts=3)
    stage3 = Stage(name="Save", workers=2, tasks=[save_data])
    
    pipeline = Pipeline(stages=[stage1, stage2, stage3], status_tracker=tracker)
    
    # 2. Define the Callback
    current_live = None

    async def on_status_change(event: StatusEvent):
        """Callback called whenever an item status changes."""
        # Update local worker state
        update_worker_state(event)
        
        if current_live:
            # Re-generate layout and refresh display
            layout = generate_layout(pipeline, tracker, num_items)
            current_live.update(layout, refresh=True)

    # Register the callback
    tracker.on_status_change = on_status_change

    # 3. Run with Live Display
    # Initialize layout
    layout = generate_layout(pipeline, tracker, num_items)
    
    with Live(layout, refresh_per_second=4, screen=True) as live:
        current_live = live
        
        # Run the pipeline directly (awaiting it)
        await pipeline.run([i for i in range(num_items)])
        
        # Final update
        current_live = None
        
    console.print("[bold green]Done![/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
