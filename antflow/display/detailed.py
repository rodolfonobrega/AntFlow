"""
Detailed dashboard using Rich library.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base import BaseDashboard

if TYPE_CHECKING:
    from ..pipeline import Pipeline
    from ..types import DashboardSnapshot, ErrorSummary, PipelineResult


class DetailedDashboard(BaseDashboard):
    """
    Detailed Rich dashboard with stage-level metrics.

    Shows:
    - Overall progress bar
    - Per-stage progress and worker counts
    - Recent errors
    - Performance metrics

    Usage:
        ```python
        results = await pipeline.run(items, dashboard="detailed")
        ```
    """

    def __init__(self, refresh_rate: float = 4.0):
        self.refresh_rate = refresh_rate
        self.total: int = 0
        self.start_time: Optional[float] = None
        self.console = Console()
        self._live: Optional[Live] = None
        self._pipeline: Optional[Pipeline] = None
        self._recent_errors: List[str] = []

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """Initialize dashboard when pipeline starts."""
        self.total = total_items
        self.start_time = time.time()
        self._pipeline = pipeline

        self._live = Live(
            self._generate_layout(pipeline.get_dashboard_snapshot()),
            console=self.console,
            refresh_per_second=self.refresh_rate,
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
            self._live.stop()

        self._print_summary(results, summary)

    def render(self, snapshot: DashboardSnapshot) -> None:
        """Render dashboard (called by on_update via base class)."""
        if self._live:
            self._live.update(self._generate_layout(snapshot))

    def _generate_layout(self, snapshot: DashboardSnapshot) -> Layout:
        """Generate the Rich layout for display."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="progress", size=5),
            Layout(name="body"),
        )

        layout["header"].update(
            Panel(
                Text("AntFlow Pipeline (Detailed)", justify="center", style="bold blue"),
                style="blue",
            )
        )

        layout["progress"].update(self._generate_progress_panel(snapshot))

        layout["body"].split_row(
            Layout(name="stages", ratio=1),
            Layout(name="metrics", ratio=1),
        )

        layout["stages"].update(self._generate_stages_panel(snapshot))
        layout["metrics"].update(self._generate_metrics_panel(snapshot))

        return layout

    def _generate_progress_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate overall progress panel."""
        stats = snapshot.pipeline_stats
        completed = stats.items_processed + stats.items_failed
        remaining = self.total - completed

        pct = (completed / self.total * 100) if self.total > 0 else 0
        bar_width = 40
        filled = int(bar_width * completed / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        if self.start_time:
            elapsed = time.time() - self.start_time
            rate = completed / elapsed if elapsed > 0 else 0
            if rate > 0 and remaining > 0:
                eta_secs = remaining / rate
                eta = self._format_time(eta_secs)
            else:
                eta = "--:--:--"
        else:
            rate = 0
            eta = "--:--:--"

        table = Table.grid(padding=(0, 1))
        table.add_column(justify="center")

        progress_text = Text()
        progress_text.append(f"[{bar}] ", style="cyan")
        progress_text.append(f"{pct:.1f}%", style="bold cyan")
        progress_text.append(f"  |  {completed}/{self.total}", style="dim")
        progress_text.append(f"  |  {rate:.1f}/s", style="green")
        progress_text.append(f"  |  ETA: {eta}", style="yellow")
        table.add_row(progress_text)

        return Panel(table, title="Progress", border_style="cyan")

    def _generate_stages_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate stages table panel."""
        table = Table(title="Stage Status", expand=True)
        table.add_column("Stage", style="cyan")
        table.add_column("Workers", style="yellow", justify="center")
        table.add_column("Pending", style="blue", justify="right")
        table.add_column("In Progress", style="yellow", justify="right")
        table.add_column("Completed", style="green", justify="right")
        table.add_column("Failed", style="red", justify="right")

        for stage_name, stage_stat in snapshot.pipeline_stats.stage_stats.items():
            total_workers = sum(
                1
                for s in snapshot.worker_states.values()
                if s.stage == stage_name
            )
            busy_workers = sum(
                1
                for s in snapshot.worker_states.values()
                if s.stage == stage_name and s.status == "busy"
            )

            table.add_row(
                stage_name,
                f"{busy_workers}/{total_workers}",
                str(stage_stat.pending_items),
                str(stage_stat.in_progress_items),
                str(stage_stat.completed_items),
                str(stage_stat.failed_items) if stage_stat.failed_items > 0 else "-",
            )

        return Panel(table, border_style="blue")

    def _generate_metrics_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate performance metrics panel."""
        table = Table(title="Performance Metrics", expand=True)
        table.add_column("Worker", style="cyan")
        table.add_column("Processed", style="green", justify="right")
        table.add_column("Failed", style="red", justify="right")
        table.add_column("Avg Time", style="yellow", justify="right")

        for worker_name, metrics in sorted(snapshot.worker_metrics.items()):
            state = snapshot.worker_states.get(worker_name)
            name_style = "bold cyan" if state and state.status == "busy" else "dim"

            table.add_row(
                Text(worker_name, style=name_style),
                str(metrics.items_processed),
                str(metrics.items_failed) if metrics.items_failed > 0 else "-",
                f"{metrics.avg_processing_time:.2f}s",
            )

        return Panel(table, border_style="green")

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _print_summary(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Print final summary after dashboard closes."""
        elapsed = time.time() - self.start_time if self.start_time else 0

        self.console.print()
        if summary.total_failed == 0:
            self.console.print(
                f"[bold green]Completed:[/bold green] {len(results)} items "
                f"in {elapsed:.1f}s"
            )
        else:
            self.console.print(
                f"[bold yellow]Completed:[/bold yellow] {len(results)} ok, "
                f"[red]{summary.total_failed} failed[/red] in {elapsed:.1f}s"
            )

            if summary.errors_by_type:
                self.console.print("\n[bold]Errors by type:[/bold]")
                for error_type, count in sorted(
                    summary.errors_by_type.items(), key=lambda x: -x[1]
                ):
                    self.console.print(f"  {error_type}: {count}")
