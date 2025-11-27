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
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)
    if random.random() < 0.1:  # 10% chance of failure
        raise ValueError("Connection timeout")
    return f"data_{item_id}"

async def process_data(data: str):
    """Simulate processing data."""
    delay = random.uniform(0.2, 0.8)
    await asyncio.sleep(delay)
    if random.random() < 0.1:
        raise ValueError("Processing error")
    return data.upper()

async def save_data(data: str):
    """Simulate saving data."""
    delay = random.uniform(0.1, 0.3)
    await asyncio.sleep(delay)
    return f"saved_{data}"

def generate_dashboard(tracker: StatusTracker, total_items: int) -> Layout:
    """Generate the dashboard layout."""
    stats = tracker.get_stats()
    
    # Main Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )
    
    # Header
    layout["header"].update(
        Panel(
            Text("AntFlow Real-Time Dashboard", justify="center", style="bold cyan"),
            style="cyan"
        )
    )
    
    # Body - Split into Stats and Recent Events
    layout["body"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="events", ratio=2)
    )
    
    # Stats Table
    stats_table = Table(title="Pipeline Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="magenta")
    
    stats_table.add_row("Total Items", str(total_items))
    stats_table.add_row("Queued", str(stats["queued"]))
    stats_table.add_row("In Progress", str(stats["in_progress"]))
    stats_table.add_row("Completed", str(stats["completed"]))
    stats_table.add_row("Failed", str(stats["failed"]))
    
    # Calculate progress
    completed_count = stats["completed"] + stats["failed"]
    progress_pct = (completed_count / total_items) * 100 if total_items > 0 else 0
    stats_table.add_row("Progress", f"{progress_pct:.1f}%")
    
    layout["stats"].update(Panel(stats_table, title="Overview"))
    
    # Recent Events (Failed items)
    events_table = Table(title="Recent Failures")
    events_table.add_column("Item ID", style="yellow")
    events_table.add_column("Stage", style="blue")
    events_table.add_column("Error", style="red")
    
    failed_events = tracker.get_by_status("failed")
    # Show last 10 failures
    for event in failed_events[-10:]:
        error_msg = str(event.metadata.get("error", "Unknown error"))
        events_table.add_row(str(event.item_id), str(event.stage), error_msg)
        
    layout["events"].update(Panel(events_table, title="Failures Log"))
    
    # Footer - Active Workers
    # In a real scenario, we'd query worker states from the pipeline if available
    # For now, just show a status message
    status_msg = "Pipeline Running..." if completed_count < total_items else "Pipeline Completed"
    layout["footer"].update(
        Panel(Text(status_msg, justify="center", style="bold green"))
    )
    
    return layout

async def main():
    # Create StatusTracker
    tracker = StatusTracker()
    
    # Define Stages
    stage1 = Stage(name="Fetch", workers=5, tasks=[fetch_data], task_attempts=2)
    stage2 = Stage(name="Process", workers=3, tasks=[process_data], task_attempts=2)
    stage3 = Stage(name="Save", workers=5, tasks=[save_data], task_attempts=2)
    
    pipeline = Pipeline(
        stages=[stage1, stage2, stage3],
        status_tracker=tracker
    )
    
    # Generate items
    num_items = 100
    items = range(num_items)
    
    # Run pipeline in background task
    task = asyncio.create_task(pipeline.run(items))
    
    # Live Dashboard Loop
    with Live(generate_dashboard(tracker, num_items), refresh_per_second=4) as live:
        while not task.done():
            live.update(generate_dashboard(tracker, num_items))
            await asyncio.sleep(0.25)
            
        # Final update
        live.update(generate_dashboard(tracker, num_items))
        
    # Get results
    results = await task
    console.print(f"\n[bold green]Processing Complete![/bold green]")
    console.print(f"Processed: {len(results)} items")
    console.print(f"Failed: {tracker.get_stats()['failed']} items")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
