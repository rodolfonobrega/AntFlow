"""
Custom Dashboard example demonstrating DashboardProtocol implementation.

Shows how to create your own dashboard by implementing the DashboardProtocol:
- on_start(pipeline, total_items): Called when pipeline starts
- on_update(snapshot): Called periodically with current state
- on_finish(results, summary): Called when pipeline completes
"""

import asyncio
import json
import random
import sys
from datetime import datetime

from antflow import Pipeline, Stage, StatusTracker


async def process_item(x: int) -> dict:
    """Simulate processing with variable delay."""
    await asyncio.sleep(random.uniform(0.1, 0.3))
    if random.random() < 0.1:
        raise ValueError("Random error")
    return {"id": x, "result": x * 2}


class SimpleDashboard:
    """Minimal dashboard that prints updates to console."""

    def on_start(self, pipeline, total_items):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting pipeline with {total_items} items")
        self.total = total_items

    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats
        pct = (stats.items_processed / self.total * 100) if self.total else 0
        sys.stdout.write(
            f"\r[{datetime.now().strftime('%H:%M:%S')}] "
            f"Progress: {pct:5.1f}% | "
            f"Done: {stats.items_processed} | "
            f"Failed: {stats.items_failed} | "
            f"In flight: {stats.items_in_flight}   "
        )
        sys.stdout.flush()

    def on_finish(self, results, summary):
        print()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Pipeline complete!")
        print(f"   Results: {len(results)}")
        print(f"   Failed: {summary.total_failed}")


class JSONDashboard:
    """Dashboard that outputs JSON for external consumption (e.g., web UI)."""

    def __init__(self, output_file=None):
        self.output_file = output_file
        self.events = []

    def _emit(self, event):
        self.events.append(event)
        if self.output_file:
            with open(self.output_file, "w") as f:
                json.dump(self.events, f, indent=2)
        else:
            print(json.dumps(event))

    def on_start(self, pipeline, total_items):
        self._emit({
            "type": "start",
            "timestamp": datetime.now().isoformat(),
            "total_items": total_items,
            "stages": [s.name for s in pipeline.stages],
        })

    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats
        self._emit({
            "type": "update",
            "timestamp": datetime.now().isoformat(),
            "processed": stats.items_processed,
            "failed": stats.items_failed,
            "in_flight": stats.items_in_flight,
            "stages": {
                name: {
                    "pending": s.pending_items,
                    "in_progress": s.in_progress_items,
                    "completed": s.completed_items,
                    "failed": s.failed_items,
                }
                for name, s in stats.stage_stats.items()
            },
        })

    def on_finish(self, results, summary):
        self._emit({
            "type": "finish",
            "timestamp": datetime.now().isoformat(),
            "total_results": len(results),
            "total_failed": summary.total_failed,
            "errors_by_type": summary.errors_by_type,
            "errors_by_stage": summary.errors_by_stage,
        })


class MultiStageDashboard:
    """Dashboard that shows per-stage progress for multi-stage pipelines."""

    def on_start(self, pipeline, total_items):
        self.total = total_items
        self.stages = [s.name for s in pipeline.stages]
        print(f"Pipeline: {' → '.join(self.stages)}")
        print(f"Processing {total_items} items\n")

    def on_update(self, snapshot):
        stats = snapshot.pipeline_stats
        completed = stats.items_processed + stats.items_failed

        pct = (completed / self.total * 100) if self.total else 0
        bar_width = 30
        filled = int(bar_width * completed / self.total) if self.total else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            f"Overall: [{bar}] {pct:5.1f}% ({completed}/{self.total} end-to-end)",
            "",
            f"{'Stage':<12} {'Pending':>8} {'Active':>8} {'Done':>8} {'Failed':>8}",
            "-" * 50,
        ]

        for stage_name, stage_stat in stats.stage_stats.items():
            lines.append(
                f"{stage_name:<12} "
                f"{stage_stat.pending_items:>8} "
                f"{stage_stat.in_progress_items:>8} "
                f"{stage_stat.completed_items:>8} "
                f"{stage_stat.failed_items:>8}"
            )

        sys.stdout.write("\r" + "\033[K" + "\n".join(lines) + "\033[F" * (len(lines) - 1))
        sys.stdout.flush()

    def on_finish(self, results, summary):
        print("\n" * 6)
        print(f"Complete! {len(results)} succeeded, {summary.total_failed} failed")
        if summary.errors_by_stage:
            print("Errors by stage:")
            for stage, count in summary.errors_by_stage.items():
                print(f"  {stage}: {count}")


async def main():
    print("=" * 60)
    print("Custom Dashboard Examples")
    print("=" * 60)

    items = list(range(20))

    print("\n1. Simple Dashboard:")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[
            Stage(name="Process", workers=3, tasks=[process_item], task_attempts=2)
        ]
    )
    results = await pipeline.run(items, custom_dashboard=SimpleDashboard())

    print("\n2. JSON Dashboard (for external UIs):")
    print("-" * 40)
    pipeline = Pipeline(
        stages=[
            Stage(name="Process", workers=3, tasks=[process_item], task_attempts=2)
        ]
    )
    json_dashboard = JSONDashboard()
    results = await pipeline.run(items[:10], custom_dashboard=json_dashboard)
    print(f"   Total events emitted: {len(json_dashboard.events)}")

    print("\n3. Multi-Stage Dashboard:")
    print("-" * 40)
    print("Shows per-stage progress for pipelines with multiple stages.\n")
    pipeline = Pipeline(
        stages=[
            Stage(name="Fetch", workers=3, tasks=[process_item], task_attempts=2),
            Stage(name="Transform", workers=2, tasks=[process_item], task_attempts=2),
            Stage(name="Save", workers=2, tasks=[process_item], task_attempts=2),
        ]
    )
    results = await pipeline.run(items, custom_dashboard=MultiStageDashboard())

    print("\n4. StatusTracker Callbacks (Event-Driven):")
    print("-" * 40)
    print("Alternative approach using callbacks instead of polling.\n")
    await run_with_callbacks()


async def run_with_callbacks():
    """Demonstrates StatusTracker callbacks as an alternative to DashboardProtocol."""
    from antflow import StatusTracker, StatusEvent

    events_log = []

    async def on_status_change(event: StatusEvent):
        events_log.append(event)
        if event.status == "failed":
            print(f"  ❌ Item {event.item_id} failed at {event.stage}")

    tracker = StatusTracker(on_status_change=on_status_change)

    pipeline = Pipeline(
        stages=[
            Stage(name="Process", workers=3, tasks=[process_item], task_attempts=1)
        ],
        tracker=tracker,
    )

    results = await pipeline.run(list(range(15)))

    print(f"  Total events captured: {len(events_log)}")
    print(f"  Results: {len(results)} succeeded")

    by_status = {}
    for e in events_log:
        by_status[e.status] = by_status.get(e.status, 0) + 1
    print(f"  Events by status: {by_status}")


if __name__ == "__main__":
    asyncio.run(main())
