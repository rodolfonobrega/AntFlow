import asyncio
import random
import time
from typing import List

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from antflow import Pipeline, Stage, StatusTracker

# Initialize Rich Console
console = Console()

async def fetch_data(item_id: int):
    """Simulate fetching data with random delays."""
    delay = random.uniform(0.5, 2.0)  # Slower to make it visible
    await asyncio.sleep(delay)
    if random.random() < 0.1:  # 10% chance of failure
        raise ValueError("Connection timeout")
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

def generate_dashboard(pipeline: Pipeline, tracker: StatusTracker, total_items: int) -> Layout:
    """Generate the dashboard layout."""
    snapshot = pipeline.get_dashboard_snapshot()
    stats = snapshot.pipeline_stats
    
    # Main Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="upper", size=12),
        Layout(name="lower")
    )
    
    # Header
    layout["header"].update(
        Panel(
            Text("AntFlow Real-Time Dashboard", justify="center", style="bold cyan"),
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
    
    # Lower Section - Item Tracker
    # We want to show all items, but prioritized by status
    items_table = Table(title="Item Tracker (All Items)", expand=True)
    items_table.add_column("ID", style="cyan", width=5)
    items_table.add_column("Status", style="white", width=12)
    items_table.add_column("Stage", style="blue", width=10)
    items_table.add_column("Worker", style="yellow", width=15)
    items_table.add_column("Info", style="dim white")

    # Get all items from tracker history/current status
    # We'll iterate through range(total_items) to show everything
    
    # Helper to get status
    for item_id in range(total_items):
        status_event = tracker.get_status(item_id)
        
        if status_event:
            status = status_event.status
            stage = status_event.stage or "-"
            worker = status_event.worker or "-"
            info = ""
            
            status_display = status.upper()
            
            if status == "failed":
                style = "red"
                info = str(status_event.metadata.get("error", ""))
            elif status == "completed":
                style = "green"
            elif status == "in_progress":
                style = "bold yellow"
            elif status == "retrying":
                style = "bold magenta"
                attempt = status_event.metadata.get("attempt", "?")
                status_display = f"RETRYING ({attempt})"
                info = str(status_event.metadata.get("error", ""))
            elif status == "queued":
                style = "blue"
            else:
                style = "white"
                
            items_table.add_row(
                str(item_id),
                Text(status_display, style=style),
                stage,
                worker,
                info
            )
        else:
            # Not started yet
            items_table.add_row(
                str(item_id),
                Text("PENDING", style="dim"),
                "-",
                "-",
                ""
            )

    layout["lower"].update(Panel(items_table, title="Tasks Status"))
    
    return layout

async def main():
    # Create StatusTracker
    tracker = StatusTracker()
    
    # Define Stages
    stage1 = Stage(name="Fetch", workers=4, tasks=[fetch_data], task_attempts=2)
    stage2 = Stage(name="Process", workers=3, tasks=[process_data], task_attempts=2)
    stage3 = Stage(name="Save", workers=2, tasks=[save_data], task_attempts=2)
    
    pipeline = Pipeline(
        stages=[stage1, stage2, stage3],
        status_tracker=tracker
    )
    
    # Generate items
    num_items = 50 # Reduced slightly to fit better on screen, but still "all"
    items = [{"id": i, "value": i} for i in range(num_items)]
    
    # Run pipeline in background task
    task = asyncio.create_task(pipeline.run(items))
    
    # Live Dashboard Loop
    try:
        with Live(generate_dashboard(pipeline, tracker, num_items), refresh_per_second=4, screen=True) as live:
            while not task.done():
                live.update(generate_dashboard(pipeline, tracker, num_items))
                await asyncio.sleep(0.2)
                
            # Final update
            live.update(generate_dashboard(pipeline, tracker, num_items))
            await asyncio.sleep(2) # Keep open for a moment
            
    except Exception as e:
        console.print(f"[red]Dashboard Error: {e}[/red]")
        
    # Get results
    try:
        results = await task
        console.print(f"\n[bold green]Processing Complete![/bold green]")
        console.print(f"Processed: {len(results)} items")
        console.print(f"Failed: {tracker.get_stats()['failed']} items")
    except Exception as e:
        console.print(f"[red]Pipeline Error: {e}[/red]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
