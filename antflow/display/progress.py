"""
Minimal terminal progress bar without external dependencies.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..pipeline import Pipeline
    from ..types import DashboardSnapshot, ErrorSummary, PipelineResult


class ProgressDisplay:
    """
    Minimal terminal progress bar that works without any dependencies.

    Displays a simple progress bar with:
    - Visual progress bar
    - Percentage complete
    - Items processed / total
    - Processing rate (items/sec)
    - Failed count (if any)

    Example:
        [████████████░░░░░░░░░░░░░░░░░░] 42% | 126/300 | 24.5/s | 2 failed

    Usage:
        ```python
        results = await pipeline.run(items, progress=True)
        ```
    """

    def __init__(
        self,
        total: int,
        width: int = 30,
        fill_char: str = "█",
        empty_char: str = "░",
    ):
        self.total = total
        self.width = width
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.start_time: Optional[float] = None
        self._last_completed = 0
        self._last_failed = 0

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """Called when pipeline starts."""
        self.total = total_items
        self.start_time = time.time()
        self._render(0, 0, 0.0)

    def on_update(self, snapshot: DashboardSnapshot) -> None:
        """Called with pipeline state updates."""
        stats = snapshot.pipeline_stats
        completed = stats.items_processed + stats.items_failed
        failed = stats.items_failed

        if self.start_time:
            elapsed = time.time() - self.start_time
            rate = completed / elapsed if elapsed > 0 else 0.0
        else:
            rate = 0.0

        self._render(completed, failed, rate)

    def on_finish(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """Called when pipeline completes."""
        completed = len(results) + summary.total_failed
        elapsed = time.time() - self.start_time if self.start_time else 0
        rate = completed / elapsed if elapsed > 0 else 0.0

        self._render(completed, summary.total_failed, rate)
        self._finish(len(results), summary.total_failed, elapsed)

    def _render(self, completed: int, failed: int, rate: float) -> None:
        """Render the progress bar to terminal."""
        if self.total == 0:
            pct = 100.0
            filled = self.width
        else:
            pct = (completed / self.total) * 100
            filled = int(self.width * completed / self.total)

        bar = self.fill_char * filled + self.empty_char * (self.width - filled)

        line = f"\r[{bar}] {pct:5.1f}% | {completed}/{self.total}"

        if rate > 0:
            line += f" | {rate:.1f}/s"

        if failed > 0:
            line += f" | {failed} failed"

        line += "   "

        sys.stdout.write(line)
        sys.stdout.flush()

    def _finish(self, processed: int, failed: int, elapsed: float) -> None:
        """Print final summary line."""
        sys.stdout.write("\n")

        if failed == 0:
            msg = f"Completed: {processed} items in {elapsed:.1f}s"
        else:
            msg = f"Completed: {processed} ok, {failed} failed in {elapsed:.1f}s"

        print(msg)
        sys.stdout.flush()
