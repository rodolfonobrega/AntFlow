"""
Full dashboard using Rich library with complete monitoring capabilities.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base import BaseDashboard

if TYPE_CHECKING:
    from ..pipeline import Pipeline
    from ..tracker import StatusTracker
    from ..types import DashboardSnapshot, ErrorSummary, PipelineResult


class FullDashboard(BaseDashboard):
    """
    Full Rich dashboard with comprehensive monitoring.

    Shows:
    - Overall progress and statistics
    - Per-stage metrics
    - Individual worker monitoring
    - Item tracking (if StatusTracker is configured)

    This is the most comprehensive dashboard option, suitable for
    debugging and detailed monitoring.

    Usage:
        ```python
        tracker = StatusTracker()
        pipeline = Pipeline(stages=[...], status_tracker=tracker)
        results = await pipeline.run(items, dashboard="full")
        ```
    """

    def __init__(self, refresh_rate: float = 4.0, max_items_shown: int = 20):
        self.refresh_rate = refresh_rate
        self.max_items_shown = max_items_shown
        self.total: int = 0
        self.start_time: Optional[float] = None
        self.console = Console()
        self._live: Optional[Live] = None
        self._pipeline: Optional[Pipeline] = None
        self._tracker: Optional[StatusTracker] = None

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """Initialize dashboard when pipeline starts."""
        self.total = total_items
        self.start_time = time.time()
        self._pipeline = pipeline
        self._tracker = getattr(pipeline, "_status_tracker", None)

        self._live = Live(
            self._generate_layout(pipeline.get_dashboard_snapshot()),
            console=self.console,
            refresh_per_second=self.refresh_rate,
            screen=True,
        )
        self._live.start()

    def on_update(self, snapshot: DashboardSnapshot) -> None:
        """Update dashboard display."""
        if self._live:
            self._live.update(self._generate_layout(snapshot))

    def on_finish(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Clean up dashboard on completion."""
        if self._live:
            if self._pipeline:
                final_snapshot = self._pipeline.get_dashboard_snapshot()
                self._live.update(self._generate_layout(final_snapshot))
                time.sleep(1)
            self._live.stop()

        self._print_summary(results, summary)

    def render(self, snapshot: DashboardSnapshot) -> None:
        """Render dashboard (called by on_update via base class)."""
        if self._live:
            self._live.update(self._generate_layout(snapshot))

    def _generate_layout(self, snapshot: DashboardSnapshot) -> Layout:
        """Generate the Rich layout for display."""
        stats = snapshot.pipeline_stats

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="upper", size=18),
            Layout(name="lower"),
        )

        layout["header"].update(
            Panel(
                Text("AntFlow Pipeline (Full)", justify="center", style="bold magenta"),
                style="magenta",
            )
        )

        layout["upper"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="workers", ratio=2),
        )

        layout["left"].split_column(
            Layout(name="overview"),
            Layout(name="stages"),
        )

        layout["overview"].update(self._generate_overview_panel(snapshot))
        layout["stages"].update(self._generate_stages_panel(snapshot))
        layout["workers"].update(self._generate_workers_panel(snapshot))
        layout["lower"].update(self._generate_items_panel(snapshot))

        return layout

    def _generate_overview_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate overview statistics panel."""
        stats = snapshot.pipeline_stats
        completed = stats.items_processed + stats.items_failed
        progress_pct = (completed / self.total * 100) if self.total > 0 else 0

        if self.start_time:
            elapsed = time.time() - self.start_time
            rate = completed / elapsed if elapsed > 0 else 0
        else:
            rate = 0

        table = Table(title="Overview", expand=True, show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta", justify="right")

        table.add_row("Total Items", str(self.total))
        table.add_row("Processed", str(stats.items_processed))
        table.add_row("Failed", str(stats.items_failed))
        table.add_row("In Flight", str(stats.items_in_flight))
        table.add_row("Progress", f"{progress_pct:.1f}%")
        table.add_row("Rate", f"{rate:.1f}/s")

        return Panel(table, border_style="blue")

    def _generate_stages_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate stage metrics panel."""
        table = Table(title="Stage Metrics", expand=True)
        table.add_column("Stage", style="cyan")
        table.add_column("Pend", style="blue", justify="right")
        table.add_column("Prog", style="yellow", justify="right")
        table.add_column("Done", style="green", justify="right")
        table.add_column("Fail", style="red", justify="right")

        for stage_name, stage_stat in snapshot.pipeline_stats.stage_stats.items():
            table.add_row(
                stage_name,
                str(stage_stat.pending_items),
                str(stage_stat.in_progress_items),
                str(stage_stat.completed_items),
                str(stage_stat.failed_items) if stage_stat.failed_items > 0 else "-",
            )

        return Panel(table, border_style="blue")

    def _generate_workers_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate worker monitoring panel."""
        table = Table(title="Worker Monitor", expand=True)
        table.add_column("Worker", style="blue")
        table.add_column("Stage", style="yellow")
        table.add_column("Status", style="white")
        table.add_column("Item", style="cyan", justify="right")
        table.add_column("Done", style="green", justify="right")
        table.add_column("Fail", style="red", justify="right")
        table.add_column("Avg(s)", style="magenta", justify="right")

        for worker_name, state in sorted(snapshot.worker_states.items()):
            metrics = snapshot.worker_metrics.get(worker_name)
            processed = metrics.items_processed if metrics else 0
            failed = metrics.items_failed if metrics else 0
            avg_time = metrics.avg_processing_time if metrics else 0.0

            status_style = "bold green" if state.status == "busy" else "dim white"
            current_item = (
                str(state.current_item_id)
                if state.current_item_id is not None
                else "-"
            )

            table.add_row(
                worker_name,
                state.stage,
                Text(state.status.upper(), style=status_style),
                current_item,
                str(processed),
                str(failed) if failed > 0 else "-",
                f"{avg_time:.2f}",
            )

        return Panel(table, border_style="green")

    def _generate_items_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate item tracking panel."""
        table = Table(title="Item Tracker", expand=True)
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Status", style="white", width=12)
        table.add_column("Stage", style="blue", width=12)
        table.add_column("Worker", style="yellow", width=14)
        table.add_column("Info", style="dim white")

        if self._tracker:
            items_to_show = min(self.total, self.max_items_shown)
            for item_id in range(items_to_show):
                status_event = self._tracker.get_status(item_id)

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
                    elif status == "skipped":
                        style = "dim cyan"
                    else:
                        style = "white"

                    table.add_row(
                        str(item_id),
                        Text(status.upper(), style=style),
                        stage,
                        worker,
                        info,
                    )
                else:
                    table.add_row(
                        str(item_id),
                        Text("PENDING", style="dim"),
                        "-",
                        "-",
                        "",
                    )

            if self.total > self.max_items_shown:
                table.add_row(
                    "...",
                    f"+{self.total - self.max_items_shown} more",
                    "",
                    "",
                    "",
                )
        else:
            table.add_row(
                "-",
                Text("No tracker", style="dim"),
                "-",
                "-",
                "Add status_tracker to Pipeline for item tracking",
            )

        return Panel(table, border_style="yellow")

    def _print_summary(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Print final summary after dashboard closes."""
        elapsed = time.time() - self.start_time if self.start_time else 0

        self.console.print()
        self.console.print("[bold]═" * 60 + "[/bold]")
        self.console.print("[bold]Pipeline Execution Summary[/bold]")
        self.console.print("[bold]═" * 60 + "[/bold]")
        self.console.print()

        if summary.total_failed == 0:
            self.console.print(
                f"[bold green]Status:[/bold green] Completed successfully"
            )
        else:
            self.console.print(
                f"[bold yellow]Status:[/bold yellow] Completed with errors"
            )

        self.console.print(f"[bold]Total items:[/bold] {self.total}")
        self.console.print(f"[bold]Processed:[/bold] {len(results)}")
        self.console.print(f"[bold]Failed:[/bold] {summary.total_failed}")
        self.console.print(f"[bold]Duration:[/bold] {elapsed:.1f}s")

        if summary.total_failed > 0:
            self.console.print()
            self.console.print("[bold red]Errors by type:[/bold red]")
            for error_type, count in sorted(
                summary.errors_by_type.items(), key=lambda x: -x[1]
            ):
                self.console.print(f"  {error_type}: {count}")

            self.console.print()
            self.console.print("[bold red]Errors by stage:[/bold red]")
            for stage, count in sorted(
                summary.errors_by_stage.items(), key=lambda x: -x[1]
            ):
                self.console.print(f"  {stage}: {count}")

        self.console.print()
