"""
Real-time dashboard using polling approach.

This dashboard periodically queries the pipeline state using
get_dashboard_snapshot() in a loop. The pipeline runs in a background task
while the main loop updates the display.

Compare with rich_callback_dashboard.py which uses event-driven callbacks.
"""

import asyncio
import random

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from antflow import Pipeline, Stage, StatusTracker
from antflow.types import DashboardSnapshot

console = Console()


async def fetch_data(item_id: int):
    """Simulate fetching data with random delays."""
    delay = random.uniform(0.3, 1.0)
    await asyncio.sleep(delay)
    if random.random() < 0.1:
        raise ValueError("Connection timeout")
    return f"data_{item_id}"


async def process_data(data: str):
    """Simulate processing data."""
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)
    if random.random() < 0.15:
        raise ValueError("Processing error")
    return data.upper()


async def save_data(data: str):
    """Simulate saving data."""
    delay = random.uniform(0.2, 0.8)
    await asyncio.sleep(delay)
    if random.random() < 0.05:
        raise ValueError("Database error")
    return f"saved_{data}"


def generate_dashboard(
    snapshot: DashboardSnapshot,
    tracker: StatusTracker,
    total_items: int
) -> Layout:
    """Generate the dashboard layout from snapshot data."""
    stats = snapshot.pipeline_stats

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="upper", size=18),
        Layout(name="lower")
    )

    layout["header"].update(
        Panel(
            Text("AntFlow Dashboard (Polling)", justify="center", style="bold cyan"),
            style="cyan"
        )
    )

    layout["upper"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="workers", ratio=2)
    )

    layout["left"].split_column(
        Layout(name="overview"),
        Layout(name="stages")
    )

    overview_table = Table(title="Overview", expand=True, show_header=False)
    overview_table.add_column("Metric", style="cyan")
    overview_table.add_column("Value", style="magenta", justify="right")

    completed = stats.items_processed + stats.items_failed
    progress_pct = (completed / total_items) * 100 if total_items > 0 else 0

    overview_table.add_row("Total Items", str(total_items))
    overview_table.add_row("Processed", str(stats.items_processed))
    overview_table.add_row("Failed", str(stats.items_failed))
    overview_table.add_row("In Flight", str(stats.items_in_flight))
    overview_table.add_row("Progress", f"{progress_pct:.1f}%")

    layout["overview"].update(Panel(overview_table, border_style="blue"))

    stage_table = Table(title="Stage Metrics", expand=True)
    stage_table.add_column("Stage", style="cyan")
    stage_table.add_column("Pend", style="blue", justify="right")
    stage_table.add_column("Prog", style="yellow", justify="right")
    stage_table.add_column("Done", style="green", justify="right")
    stage_table.add_column("Fail", style="red", justify="right")

    for stage_name, stage_stat in stats.stage_stats.items():
        stage_table.add_row(
            stage_name,
            str(stage_stat.pending_items),
            str(stage_stat.in_progress_items),
            str(stage_stat.completed_items),
            str(stage_stat.failed_items)
        )

    layout["stages"].update(Panel(stage_table, border_style="blue"))

    worker_table = Table(title="Worker Monitor", expand=True)
    worker_table.add_column("Worker", style="blue")
    worker_table.add_column("Stage", style="yellow")
    worker_table.add_column("Status", style="white")
    worker_table.add_column("Item", style="cyan", justify="right")
    worker_table.add_column("Done", style="green", justify="right")
    worker_table.add_column("Fail", style="red", justify="right")
    worker_table.add_column("Avg(s)", style="magenta", justify="right")

    for worker_name, state in sorted(snapshot.worker_states.items()):
        metrics = snapshot.worker_metrics.get(worker_name)
        processed = metrics.items_processed if metrics else 0
        failed = metrics.items_failed if metrics else 0
        avg_time = metrics.avg_processing_time if metrics else 0.0

        status_style = "bold green" if state.status == "busy" else "dim white"
        current_item = str(state.current_item_id) if state.current_item_id is not None else "-"

        worker_table.add_row(
            worker_name,
            state.stage,
            Text(state.status.upper(), style=status_style),
            current_item,
            str(processed),
            str(failed),
            f"{avg_time:.2f}"
        )

    layout["workers"].update(Panel(worker_table, border_style="green"))

    items_table = Table(title="Item Tracker", expand=True)
    items_table.add_column("ID", style="cyan", width=5)
    items_table.add_column("Status", style="white", width=12)
    items_table.add_column("Stage", style="blue", width=10)
    items_table.add_column("Worker", style="yellow", width=12)
    items_table.add_column("Info", style="dim white")

    for item_id in range(total_items):
        status_event = tracker.get_status(item_id)

        if status_event:
            status = status_event.status
            stage = status_event.stage or "-"
            worker = status_event.worker or "-"
            info = ""

            if status == "failed":
                style = "red"
                info = str(status_event.metadata.get("error", ""))[:30]
            elif status == "completed":
                style = "green"
            elif status == "in_progress":
                style = "bold yellow"
            elif status == "retrying":
                style = "bold magenta"
                attempt = status_event.metadata.get("attempt", 1)
                info = f"attempt {attempt}"
            elif status == "queued":
                style = "blue"
            else:
                style = "white"

            items_table.add_row(
                str(item_id),
                Text(status.upper(), style=style),
                stage,
                worker,
                info
            )
        else:
            items_table.add_row(
                str(item_id),
                Text("PENDING", style="dim"),
                "-",
                "-",
                ""
            )

    layout["lower"].update(Panel(items_table, border_style="yellow"))

    return layout


async def main():
    num_items = 30
    tracker = StatusTracker()

    stage1 = Stage(
        name="Fetch",
        workers=4,
        tasks=[fetch_data],
        task_attempts=2,
        task_wait_seconds=0.1
    )

    stage2 = Stage(
        name="Process",
        workers=3,
        tasks=[process_data],
        retry="per_stage",
        stage_attempts=3,
        task_wait_seconds=0.2
    )

    stage3 = Stage(
        name="Save",
        workers=2,
        tasks=[save_data],
        task_attempts=2,
        task_wait_seconds=0.1
    )

    pipeline = Pipeline(
        stages=[stage1, stage2, stage3],
        status_tracker=tracker
    )

    items = list(range(num_items))

    pipeline_task = asyncio.create_task(pipeline.run(items))

    try:
        initial_snapshot = pipeline.get_dashboard_snapshot()
        initial_layout = generate_dashboard(initial_snapshot, tracker, num_items)

        with Live(initial_layout, refresh_per_second=4, screen=True) as live:
            while not pipeline_task.done():
                snapshot = pipeline.get_dashboard_snapshot()
                live.update(generate_dashboard(snapshot, tracker, num_items))
                await asyncio.sleep(0.25)

            snapshot = pipeline.get_dashboard_snapshot()
            live.update(generate_dashboard(snapshot, tracker, num_items))
            await asyncio.sleep(2)

    except Exception as e:
        console.print(f"[red]Dashboard Error: {e}[/red]")

    try:
        results = await pipeline_task
        console.print("\n[bold green]Processing Complete![/bold green]")
        console.print(f"Processed: {len(results)} items")
        console.print(f"Failed: {tracker.get_stats()['failed']} items")
    except Exception as e:
        console.print(f"[red]Pipeline Error: {e}[/red]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
