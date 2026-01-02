"""Tests for display module (progress bar and dashboards)."""

import asyncio
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from antflow import Pipeline, Stage, StatusTracker
from antflow.display import (
    BaseDashboard,
    CompactDashboard,
    DetailedDashboard,
    FullDashboard,
    ProgressDisplay,
)
from antflow.types import DashboardSnapshot, ErrorSummary, PipelineStats


async def fast_task(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


class TestProgressDisplay:
    """Tests for ProgressDisplay class."""

    def test_progress_init(self):
        """ProgressDisplay initializes correctly."""
        progress = ProgressDisplay(total=100)

        assert progress.total == 100
        assert progress.width == 30
        assert progress.start_time is None

    def test_progress_on_start_sets_time(self):
        """on_start sets the start time."""
        pipeline = MagicMock()
        progress = ProgressDisplay(total=0)

        progress.on_start(pipeline, 100)

        assert progress.total == 100
        assert progress.start_time is not None

    @pytest.mark.asyncio
    async def test_progress_with_pipeline(self):
        """ProgressDisplay works with Pipeline.run()."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[fast_task])]
        )

        with patch("sys.stdout", new_callable=StringIO):
            results = await pipeline.run(list(range(10)), progress=True)

        assert len(results) == 10


class TestBaseDashboard:
    """Tests for BaseDashboard abstract class."""

    def test_base_dashboard_requires_render(self):
        """BaseDashboard requires render() implementation."""
        with pytest.raises(TypeError):
            BaseDashboard()

    def test_base_dashboard_subclass(self):
        """BaseDashboard can be subclassed."""

        class MyDashboard(BaseDashboard):
            def render(self, snapshot):
                pass

        dashboard = MyDashboard()
        assert dashboard is not None


class TestCompactDashboard:
    """Tests for CompactDashboard class."""

    def test_compact_dashboard_init(self):
        """CompactDashboard initializes correctly."""
        dashboard = CompactDashboard()

        assert dashboard.refresh_rate == 4.0
        assert dashboard.total == 0
        assert dashboard._live is None

    @pytest.mark.asyncio
    async def test_compact_dashboard_with_pipeline(self):
        """CompactDashboard works with Pipeline.run()."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[fast_task])]
        )

        results = await pipeline.run(list(range(5)), dashboard="compact")

        assert len(results) == 5


class TestDetailedDashboard:
    """Tests for DetailedDashboard class."""

    def test_detailed_dashboard_init(self):
        """DetailedDashboard initializes correctly."""
        dashboard = DetailedDashboard()

        assert dashboard.refresh_rate == 4.0
        assert dashboard.total == 0

    @pytest.mark.asyncio
    async def test_detailed_dashboard_with_pipeline(self):
        """DetailedDashboard works with Pipeline.run()."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[fast_task])]
        )

        results = await pipeline.run(list(range(5)), dashboard="detailed")

        assert len(results) == 5


class TestFullDashboard:
    """Tests for FullDashboard class."""

    def test_full_dashboard_init(self):
        """FullDashboard initializes correctly."""
        dashboard = FullDashboard()

        assert dashboard.refresh_rate == 4.0
        assert dashboard.max_items_shown == 20
        assert dashboard.total == 0

    @pytest.mark.asyncio
    async def test_full_dashboard_with_pipeline(self):
        """FullDashboard works with Pipeline.run()."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[fast_task])],
            status_tracker=tracker,
        )

        results = await pipeline.run(list(range(5)), dashboard="full")

        assert len(results) == 5


class TestCustomDashboard:
    """Tests for custom dashboard implementations."""

    @pytest.mark.asyncio
    async def test_custom_dashboard_protocol(self):
        """Custom dashboard implementing DashboardProtocol works."""
        events = []

        class MyDashboard:
            def on_start(self, pipeline, total_items):
                events.append(("start", total_items))

            def on_update(self, snapshot):
                events.append(("update", snapshot.pipeline_stats.items_processed))

            def on_finish(self, results, summary):
                events.append(("finish", len(results)))

        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=3, tasks=[fast_task])]
        )

        results = await pipeline.run(
            list(range(5)),
            custom_dashboard=MyDashboard(),
        )

        assert len(results) == 5
        assert events[0] == ("start", 5)
        assert events[-1] == ("finish", 5)
        assert any(e[0] == "update" for e in events)

    @pytest.mark.asyncio
    async def test_progress_and_dashboard_mutual_exclusion(self):
        """Cannot use both progress and dashboard parameters."""
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=2, tasks=[fast_task])]
        )

        with pytest.raises(ValueError, match="Cannot use both"):
            await pipeline.run(
                list(range(5)),
                progress=True,
                dashboard="compact",
            )
