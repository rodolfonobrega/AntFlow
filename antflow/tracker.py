from __future__ import annotations

from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .types import ErrorSummary, FailedItem, StatusEvent, StatusType, TaskEvent


class StatusTracker:
    """
    Tracks status changes for items flowing through a pipeline.

    Provides methods to query current status, filter by status,
    get statistics, and retrieve event history.

    Example:
        ```python
        tracker = StatusTracker()

        async def on_change(event: StatusEvent):
            print(f"Item {event.item_id}: {event.status}")

        tracker.on_status_change = on_change
        pipeline = Pipeline(stages=[...], status_tracker=tracker)

        results = await pipeline.run(items)
        print(tracker.get_stats())
        ```
    """

    def __init__(
        self,
        on_status_change: Optional[Callable[[StatusEvent], Awaitable[None]]] = None,
        on_task_start: Optional[Callable[[TaskEvent], Awaitable[None]]] = None,
        on_task_complete: Optional[Callable[[TaskEvent], Awaitable[None]]] = None,
        on_task_retry: Optional[Callable[[TaskEvent], Awaitable[None]]] = None,
        on_task_fail: Optional[Callable[[TaskEvent], Awaitable[None]]] = None,
    ):
        """
        Initialize the status tracker.

        Args:
            on_status_change: Optional callback invoked on each item [StatusEvent][antflow.types.StatusEvent]
            on_task_start: Optional callback when a task starts executing ([TaskEvent][antflow.types.TaskEvent])
            on_task_complete: Optional callback when a task completes successfully ([TaskEvent][antflow.types.TaskEvent])
            on_task_retry: Optional callback when a task is retrying after failure ([TaskEvent][antflow.types.TaskEvent])
            on_task_fail: Optional callback when a task fails after all retries ([TaskEvent][antflow.types.TaskEvent])
        """
        self.on_status_change = on_status_change
        self.on_task_start = on_task_start
        self.on_task_complete = on_task_complete
        self.on_task_retry = on_task_retry
        self.on_task_fail = on_task_fail
        self._history: Dict[Any, List[StatusEvent]] = {}
        self._current_status: Dict[Any, StatusEvent] = {}

    async def _emit(self, event: StatusEvent) -> None:
        """
        Internal method to record and emit a status event.

        Args:
            event: The [StatusEvent][antflow.types.StatusEvent] to emit
        """
        if event.item_id not in self._history:
            self._history[event.item_id] = []

        self._history[event.item_id].append(event)
        self._current_status[event.item_id] = event

        if self.on_status_change:
            await self.on_status_change(event)

    async def _emit_task_event(self, event: TaskEvent) -> None:
        """
        Internal method to emit a task-level event.

        Args:
            event: The [TaskEvent][antflow.types.TaskEvent] to emit
        """
        if event.event_type == "start" and self.on_task_start:
            await self.on_task_start(event)
        elif event.event_type == "complete" and self.on_task_complete:
            await self.on_task_complete(event)
        elif event.event_type == "retry" and self.on_task_retry:
            await self.on_task_retry(event)
        elif event.event_type == "fail" and self.on_task_fail:
            await self.on_task_fail(event)

    def get_status(self, item_id: Any) -> StatusEvent | None:
        """
        Get the current status of an item.

        Args:
            item_id: The item identifier

        Returns:
            The most recent [StatusEvent][antflow.types.StatusEvent] for the item, or None if not found
        """
        return self._current_status.get(item_id)

    def get_by_status(self, status: StatusType) -> List[StatusEvent]:
        """
        Get all items currently in a given status.

        Args:
            status: The status to filter by

        Returns:
            List of [StatusEvents][antflow.types.StatusEvent] for items with the given status
        """
        return [event for event in self._current_status.values() if event.status == status]

    def get_stats(self) -> Dict[str, int]:
        """
        Get aggregate statistics by status.

        Returns:
            Dictionary mapping status names to counts
        """
        stats: Dict[str, int] = {"queued": 0, "in_progress": 0, "completed": 0, "failed": 0}

        for event in self._current_status.values():
            stats[event.status] += 1

        return stats

    def get_history(self, item_id: Any) -> List[StatusEvent]:
        """
        Get the full event history for an item.

        Args:
            item_id: The item identifier

        Returns:
            List of all [StatusEvents][antflow.types.StatusEvent] for the item, in chronological order
        """
        return self._history.get(item_id, [])

    def get_failed_items(self) -> List[FailedItem]:
        """
        Get details of all failed items.

        Returns:
            List of [FailedItem][antflow.types.FailedItem] with failure details
        """
        failed_items = []

        for item_id, event in self._current_status.items():
            if event.status != "failed":
                continue

            history = self._history.get(item_id, [])
            attempts = sum(1 for e in history if e.status == "retrying") + 1

            error_str = str(event.metadata.get("error", "Unknown error"))
            error_type = "Exception"

            if ":" in error_str:
                parts = error_str.split(":", 1)
                if parts[0].replace("_", "").replace(" ", "").isalpha():
                    error_type = parts[0].strip()

            failed_items.append(
                FailedItem(
                    item_id=item_id,
                    error=error_str,
                    error_type=error_type,
                    stage=event.stage or "unknown",
                    attempts=attempts,
                    timestamp=event.timestamp,
                )
            )

        return failed_items

    def get_error_summary(self) -> ErrorSummary:
        """
        Get aggregated error information.

        Returns:
            [ErrorSummary][antflow.types.ErrorSummary] with failure statistics and details

        Example:
            ```python
            summary = tracker.get_error_summary()
            print(f"Total failed: {summary.total_failed}")
            for error_type, count in summary.errors_by_type.items():
                print(f"  {error_type}: {count}")
            ```
        """
        failed_items = self.get_failed_items()

        errors_by_type: Dict[str, int] = defaultdict(int)
        errors_by_stage: Dict[str, int] = defaultdict(int)

        for item in failed_items:
            errors_by_type[item.error_type] += 1
            errors_by_stage[item.stage] += 1

        return ErrorSummary(
            total_failed=len(failed_items),
            errors_by_type=dict(errors_by_type),
            errors_by_stage=dict(errors_by_stage),
            failed_items=failed_items,
        )
