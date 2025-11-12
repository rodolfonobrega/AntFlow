import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .pipeline import Pipeline
from .tracker import StatusEvent, StatusTracker
from .types import DashboardSnapshot, PipelineStats, WorkerMetrics, WorkerState


class PipelineDashboard:
    """
    Dashboard helper for real-time pipeline monitoring.

    Combines pull-based queries with push-based events for efficient dashboards.
    Maintains internal state updated via events and provides snapshot queries.

    Example:
        >>> async def on_update(snapshot):
        ...     print(f"Active workers: {sum(1 for s in snapshot.worker_states.values() if s.status == 'busy')}")
        >>>
        >>> tracker = StatusTracker()
        >>> pipeline = Pipeline(stages=[stage], status_tracker=tracker)
        >>> dashboard = PipelineDashboard(pipeline, tracker, on_update=on_update)
        >>>
        >>> results = await pipeline.run(items)
    """

    def __init__(
        self,
        pipeline: Pipeline,
        tracker: StatusTracker,
        on_update: Optional[Callable[[DashboardSnapshot], Awaitable[None]]] = None,
        update_interval: float = 1.0
    ):
        """
        Initialize dashboard.

        Args:
            pipeline: Pipeline instance to monitor
            tracker: StatusTracker instance tracking pipeline events
            on_update: Optional callback invoked with snapshot on updates
            update_interval: Seconds between automatic updates (0 to disable)
        """
        self.pipeline = pipeline
        self.tracker = tracker
        self.on_update = on_update
        self.update_interval = update_interval

        self._original_callback = tracker.on_status_change
        self._subscribers: Set[Callable[[StatusEvent], Awaitable[None]]] = set()
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_monitoring = asyncio.Event()

        tracker.on_status_change = self._handle_status_change

    async def _handle_status_change(self, event: StatusEvent) -> None:
        """Internal handler that wraps original callback and notifies subscribers."""
        if self._original_callback:
            await self._original_callback(event)

        for subscriber in self._subscribers:
            try:
                await subscriber(event)
            except Exception:
                pass

    def subscribe(
        self,
        callback: Callable[[StatusEvent], Awaitable[None]]
    ) -> None:
        """
        Subscribe to status change events.

        Args:
            callback: Async function called on each status change

        Example:
            >>> async def on_event(event):
            ...     if event.status == "failed":
            ...         print(f"Item {event.item_id} failed!")
            >>> dashboard.subscribe(on_event)
        """
        self._subscribers.add(callback)

    def unsubscribe(
        self,
        callback: Callable[[StatusEvent], Awaitable[None]]
    ) -> None:
        """
        Unsubscribe from status change events.

        Args:
            callback: Previously subscribed callback to remove
        """
        self._subscribers.discard(callback)

    def get_snapshot(self) -> DashboardSnapshot:
        """
        Get current dashboard snapshot.

        Returns:
            DashboardSnapshot with complete current state

        Example:
            >>> snapshot = dashboard.get_snapshot()
            >>> busy_workers = [w for w, s in snapshot.worker_states.items() if s.status == "busy"]
            >>> print(f"Busy workers: {len(busy_workers)}")
        """
        return self.pipeline.get_dashboard_snapshot()

    def get_worker_states(self) -> Dict[str, WorkerState]:
        """Get current state of all workers."""
        return self.pipeline.get_worker_states()

    def get_worker_metrics(self) -> Dict[str, WorkerMetrics]:
        """Get performance metrics for all workers."""
        return self.pipeline.get_worker_metrics()

    def get_stats(self) -> PipelineStats:
        """Get pipeline statistics."""
        return self.pipeline.get_stats()

    def get_active_workers(self) -> List[str]:
        """
        Get list of currently busy worker names.

        Returns:
            List of worker names currently processing items
        """
        states = self.get_worker_states()
        return [
            name for name, state in states.items()
            if state.status == "busy"
        ]

    def get_idle_workers(self) -> List[str]:
        """
        Get list of currently idle worker names.

        Returns:
            List of worker names waiting for work
        """
        states = self.get_worker_states()
        return [
            name for name, state in states.items()
            if state.status == "idle"
        ]

    def get_worker_utilization(self) -> Dict[str, float]:
        """
        Calculate utilization percentage for each worker.

        Returns:
            Dictionary mapping worker name to utilization (0.0 to 1.0)

        Note:
            Utilization = items_processed / (items_processed + items_failed)
            Returns 0.0 for workers that haven't processed any items.
        """
        metrics = self.get_worker_metrics()
        utilization = {}

        for name, metric in metrics.items():
            total = metric.items_processed + metric.items_failed
            if total == 0:
                utilization[name] = 0.0
            else:
                utilization[name] = metric.items_processed / total

        return utilization

    async def start_monitoring(self) -> None:
        """
        Start automatic periodic updates.

        If update_interval > 0 and on_update callback is set,
        calls on_update with snapshot at regular intervals.

        Example:
            >>> await dashboard.start_monitoring()
        """
        if self.update_interval <= 0 or not self.on_update:
            return

        if self._monitor_task and not self._monitor_task.done():
            return

        self._stop_monitoring.clear()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """
        Stop automatic periodic updates.

        Example:
            >>> await dashboard.stop_monitoring()
        """
        self._stop_monitoring.set()

        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=self.update_interval + 1.0)
            except asyncio.TimeoutError:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

    async def _monitor_loop(self) -> None:
        """Internal monitoring loop that calls on_update periodically."""
        while not self._stop_monitoring.is_set():
            try:
                snapshot = self.get_snapshot()
                if self.on_update:
                    await self.on_update(snapshot)
            except Exception:
                pass

            try:
                await asyncio.wait_for(
                    self._stop_monitoring.wait(),
                    timeout=self.update_interval
                )
                break
            except asyncio.TimeoutError:
                continue

    async def __aenter__(self) -> "PipelineDashboard":
        """Context manager entry - starts monitoring."""
        await self.start_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops monitoring."""
        await self.stop_monitoring()
