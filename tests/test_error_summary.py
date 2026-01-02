"""Tests for ErrorSummary and get_error_summary()."""

import asyncio

import pytest

from antflow import Pipeline, Stage, StatusTracker
from antflow.types import ErrorSummary, FailedItem


async def always_fail(x: int) -> int:
    raise ValueError(f"Error for {x}")


async def sometimes_fail(x: int) -> int:
    await asyncio.sleep(0.01)
    if x % 2 == 0:
        raise ConnectionError(f"Connection failed for {x}")
    return x * 2


async def success(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


class TestErrorSummary:
    """Tests for ErrorSummary dataclass."""

    def test_error_summary_str_no_errors(self):
        """ErrorSummary string representation with no errors."""
        summary = ErrorSummary(
            total_failed=0,
            errors_by_type={},
            errors_by_stage={},
            failed_items=[],
        )

        assert str(summary) == "No errors occurred"

    def test_error_summary_str_with_errors(self):
        """ErrorSummary string representation with errors."""
        summary = ErrorSummary(
            total_failed=5,
            errors_by_type={"ValueError": 3, "ConnectionError": 2},
            errors_by_stage={"Fetch": 4, "Process": 1},
            failed_items=[],
        )

        result = str(summary)
        assert "5 failed items" in result
        assert "ValueError: 3" in result
        assert "ConnectionError: 2" in result
        assert "Fetch: 4" in result
        assert "Process: 1" in result


class TestGetErrorSummary:
    """Tests for get_error_summary() method."""

    @pytest.mark.asyncio
    async def test_get_error_summary_no_tracker(self):
        """get_error_summary() without tracker returns basic summary."""
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[always_fail], task_attempts=1)
            ]
        )

        await pipeline.run(list(range(3)))
        summary = pipeline.get_error_summary()

        assert summary.total_failed == 3
        assert summary.errors_by_type == {}
        assert summary.errors_by_stage == {}

    @pytest.mark.asyncio
    async def test_get_error_summary_with_tracker(self):
        """get_error_summary() with tracker returns detailed summary."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[always_fail], task_attempts=1)
            ],
            status_tracker=tracker,
        )

        await pipeline.run(list(range(3)))
        summary = pipeline.get_error_summary()

        assert summary.total_failed == 3
        assert "Process" in summary.errors_by_stage
        assert len(summary.failed_items) == 3

    @pytest.mark.asyncio
    async def test_get_error_summary_mixed_results(self):
        """get_error_summary() with mixed success/failure."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[
                Stage(
                    name="Process",
                    workers=3,
                    tasks=[sometimes_fail],
                    task_attempts=1,
                )
            ],
            status_tracker=tracker,
        )

        await pipeline.run(list(range(6)))
        summary = pipeline.get_error_summary()

        assert summary.total_failed == 3
        assert summary.errors_by_stage["Process"] == 3

    @pytest.mark.asyncio
    async def test_get_error_summary_no_failures(self):
        """get_error_summary() with no failures."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[Stage(name="Process", workers=2, tasks=[success])],
            status_tracker=tracker,
        )

        await pipeline.run(list(range(5)))
        summary = pipeline.get_error_summary()

        assert summary.total_failed == 0
        assert summary.errors_by_type == {}
        assert summary.errors_by_stage == {}
        assert summary.failed_items == []


class TestTrackerGetErrorSummary:
    """Tests for StatusTracker.get_error_summary() method."""

    @pytest.mark.asyncio
    async def test_tracker_get_failed_items(self):
        """StatusTracker.get_failed_items() returns FailedItem list."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[always_fail], task_attempts=1)
            ],
            status_tracker=tracker,
        )

        await pipeline.run(list(range(3)))
        failed_items = tracker.get_failed_items()

        assert len(failed_items) == 3
        for item in failed_items:
            assert isinstance(item, FailedItem)
            assert item.stage == "Process"
            assert item.attempts >= 1

    @pytest.mark.asyncio
    async def test_tracker_error_summary(self):
        """StatusTracker.get_error_summary() returns ErrorSummary."""
        tracker = StatusTracker()
        pipeline = Pipeline(
            stages=[
                Stage(name="Process", workers=2, tasks=[always_fail], task_attempts=1)
            ],
            status_tracker=tracker,
        )

        await pipeline.run(list(range(3)))
        summary = tracker.get_error_summary()

        assert isinstance(summary, ErrorSummary)
        assert summary.total_failed == 3
