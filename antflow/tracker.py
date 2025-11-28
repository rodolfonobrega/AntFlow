from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from .types import TaskEvent

StatusType = Literal["queued", "in_progress", "completed", "failed"]


@dataclass
class StatusEvent:
    """
    Represents a status change event for an item in the pipeline.

    Attributes:
        item_id: Unique identifier for the item
        stage: Name of the stage (None if not stage-specific)
        status: Current status of the item
        worker: Name of the worker processing the item (if applicable)
        timestamp: Unix timestamp when the event occurred
        metadata: Additional metadata about the event
    """
    item_id: Any
    stage: str | None
    status: StatusType
    worker: str | None
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def worker_id(self) -> int | None:
        """
        Extract worker ID from worker name.

        Examples:
            "ProcessBatch-W5" -> 5
            "Fetch-W0" -> 0
            None -> None

        Returns:
            Worker ID (0-indexed) or None if not available
        """
        if self.worker:
            try:
                return int(self.worker.split('-W')[-1])
            except (ValueError, IndexError):
                return None
        return None


class StatusTracker:
    """
    Tracks status changes for items flowing through a pipeline.

    Provides methods to query current status, filter by status,
    get statistics, and retrieve event history.

    Example:
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
        on_task_fail: Optional[Callable[[TaskEvent], Awaitable[None]]] = None
    ):
        """
        Initialize the status tracker.

        Args:
            on_status_change: Optional callback invoked on each item status change
            on_task_start: Optional callback when a task starts executing
            on_task_complete: Optional callback when a task completes successfully
            on_task_retry: Optional callback when a task is retrying after failure
            on_task_fail: Optional callback when a task fails after all retries
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
            event: The status event to emit
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
            event: The task event to emit
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
            The most recent StatusEvent for the item, or None if not found
        """
        return self._current_status.get(item_id)

    def get_by_status(self, status: StatusType) -> List[StatusEvent]:
        """
        Get all items currently in a given status.

        Args:
            status: The status to filter by

        Returns:
            List of StatusEvents for items with the given status
        """
        return [
            event for event in self._current_status.values()
            if event.status == status
        ]

    def get_stats(self) -> Dict[str, int]:
        """
        Get aggregate statistics by status.

        Returns:
            Dictionary mapping status names to counts
        """
        stats: Dict[str, int] = {
            "queued": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0
        }

        for event in self._current_status.values():
            stats[event.status] += 1

        return stats

    def get_history(self, item_id: Any) -> List[StatusEvent]:
        """
        Get the full event history for an item.

        Args:
            item_id: The item identifier

        Returns:
            List of all StatusEvents for the item, in chronological order
        """
        return self._history.get(item_id, [])
