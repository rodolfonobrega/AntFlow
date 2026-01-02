"""
Compact dashboard using Rich library.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base import BaseDashboard

if TYPE_CHECKING:
    from ..pipeline import Pipeline
    from ..types import DashboardSnapshot, ErrorSummary, PipelineResult


class CompactDashboard(BaseDashboard):
    """
    Compact Rich dashboard showing essential pipeline metrics.

    Displays a single panel with:
    - Progress bar
    - Current stage activity
    - Processing rate and ETA
    - Success/failure counts

    Example output:
        ╭───────────────── AntFlow Pipeline ─────────────────╮
        │  [████████████░░░░░░░░░░░░░░░░░░] 42%              │
        │  Stage: Process (3/5 workers busy)                 │
        │  Rate: 24.5 items/sec | ETA: 00:02:15              │
        │  OK: 126 | Failed: 2 | Remaining: 172              │
        ╰────────────────────────────────────────────────────╯

    Usage:
        ```python
        results = await pipeline.run(items, dashboard="compact")
        ```
    """

    def __init__(self, refresh_rate: float = 4.0):
        self.refresh_rate = refresh_rate
        self.total: int = 0
        self.start_time: Optional[float] = None
        self.console = Console()
        self._live: Optional[Live] = None
        self._pipeline: Optional[Pipeline] = None

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """Initialize dashboard when pipeline starts."""
        self.total = total_items
        self.start_time = time.time()
        self._pipeline = pipeline

        self._live = Live(
            self._generate_panel(pipeline.get_dashboard_snapshot()),
            console=self.console,
            refresh_per_second=self.refresh_rate,
        )
        self._live.start()

    def on_update(self, snapshot: DashboardSnapshot) -> None:
        """Update dashboard display."""
        if self._live:
            self._live.update(self._generate_panel(snapshot))

    def on_finish(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Clean up dashboard on completion."""
        if self._live:
            if self._pipeline:
                final_snapshot = self._pipeline.get_dashboard_snapshot()
                self._live.update(self._generate_panel(final_snapshot))
            self._live.stop()

        self._print_summary(results, summary)

    def render(self, snapshot: DashboardSnapshot) -> None:
        """Render dashboard (called by on_update via base class)."""
        if self._live:
            self._live.update(self._generate_panel(snapshot))

    def _generate_panel(self, snapshot: DashboardSnapshot) -> Panel:
        """Generate the Rich panel for display."""
        stats = snapshot.pipeline_stats
        completed = stats.items_processed + stats.items_failed
        remaining = self.total - completed

        pct = (completed / self.total * 100) if self.total > 0 else 0
        bar_width = 30
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

        stage_info = self._get_stage_info(snapshot)

        table = Table.grid(padding=(0, 1))
        table.add_column(justify="left")

        progress_text = Text()
        progress_text.append(f"  [{bar}] ", style="cyan")
        progress_text.append(f"{pct:.0f}%", style="bold cyan")
        table.add_row(progress_text)

        table.add_row(Text(f"  {stage_info}", style="yellow"))

        rate_text = Text()
        rate_text.append(f"  Rate: ", style="dim")
        rate_text.append(f"{rate:.1f}", style="green")
        rate_text.append(" items/sec | ETA: ", style="dim")
        rate_text.append(eta, style="green")
        table.add_row(rate_text)

        status_text = Text()
        status_text.append("  OK: ", style="dim")
        status_text.append(str(stats.items_processed), style="green")
        status_text.append(" | Failed: ", style="dim")
        fail_style = "red" if stats.items_failed > 0 else "dim"
        status_text.append(str(stats.items_failed), style=fail_style)
        status_text.append(" | Remaining: ", style="dim")
        status_text.append(str(remaining), style="blue")
        table.add_row(status_text)

        return Panel(
            table,
            title="[bold]AntFlow Pipeline[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )

    def _get_stage_info(self, snapshot: DashboardSnapshot) -> str:
        """Get current stage activity summary."""
        stages_info = []

        for stage_name, stage_stat in snapshot.pipeline_stats.stage_stats.items():
            busy = stage_stat.in_progress_items
            if busy > 0 or stage_stat.pending_items > 0:
                total_workers = sum(
                    1
                    for s in snapshot.worker_states.values()
                    if s.stage == stage_name
                )
                stages_info.append(f"{stage_name} ({busy}/{total_workers} busy)")

        if stages_info:
            return "Stage: " + ", ".join(stages_info)
        return "Stage: idle"

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
