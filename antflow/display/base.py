"""
Base classes for dashboard implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..pipeline import Pipeline
    from ..types import DashboardSnapshot, ErrorSummary, PipelineResult


class BaseDashboard(ABC):
    """
    Abstract base class for built-in dashboards.

    Subclass this to create custom dashboards with full control over rendering.
    For simpler use cases, implement the DashboardProtocol instead.

    Example:
        ```python
        class MyDashboard(BaseDashboard):
            def on_start(self, pipeline, total_items):
                self.total = total_items
                print("Starting...")

            def on_update(self, snapshot):
                self.render(snapshot)

            def on_finish(self, results, summary):
                print(f"Done: {len(results)} results")

            def render(self, snapshot):
                stats = snapshot.pipeline_stats
                print(f"Progress: {stats.items_processed}/{self.total}")
        ```
    """

    def on_start(self, pipeline: Pipeline, total_items: int) -> None:
        """
        Called when pipeline execution starts.

        Args:
            pipeline: The Pipeline instance
            total_items: Total number of items to process
        """
        pass

    def on_update(self, snapshot: DashboardSnapshot) -> None:
        """
        Called periodically with current pipeline state.

        Args:
            snapshot: Current state snapshot
        """
        self.render(snapshot)

    def on_finish(
        self, results: List[PipelineResult], summary: ErrorSummary
    ) -> None:
        """
        Called when pipeline execution completes.

        Args:
            results: List of pipeline results
            summary: Error summary with failure details
        """
        pass

    @abstractmethod
    def render(self, snapshot: DashboardSnapshot) -> None:
        """
        Render the dashboard display.

        Args:
            snapshot: Current pipeline state to display
        """
        ...
