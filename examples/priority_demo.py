"""
Priority queue demonstration example.

Shows how items with different priorities are processed in priority order.
Lower priority numbers are processed first (0 = highest priority).

Key concepts:
- Items can be fed with different priority levels
- Priority queue ensures high-priority items jump ahead
- Single worker makes processing order deterministic
- StatusTracker callback tracks actual processing order
"""

import asyncio

from antflow import Pipeline, Stage, StatusEvent, StatusTracker


async def process_item(value: str) -> str:
    """Process a value with a small delay to allow queue buildup."""
    await asyncio.sleep(0.15)
    return f"Processed {value}"


async def main():
    print("=" * 60)
    print("Priority Queue Demonstration")
    print("=" * 60)
    print()
    print("Priority levels (lower = higher priority):")
    print("  - 0: Critical (highest)")
    print("  - 10: High")
    print("  - 100: Normal (default)")
    print("  - 500: Low")
    print()

    processing_order = []

    async def on_status_change(event: StatusEvent):
        """Track the order items are processed."""
        if event.status == "completed":
            processing_order.append(event.item_id)

    tracker = StatusTracker(on_status_change=on_status_change)

    stage = Stage(
        name="Processing",
        workers=1,
        tasks=[process_item]
    )

    pipeline = Pipeline(stages=[stage], status_tracker=tracker)

    await pipeline.start()

    print("--- Feeding Blocker ---")
    await pipeline.feed([{"id": "blocker", "value": "BLOCKER"}], priority=100)
    await asyncio.sleep(0.05)

    print("--- Feeding Mixed Priorities ---")

    await pipeline.feed([{"id": "low", "value": "LowPrio"}], priority=500)
    print("Fed: Low priority (500)")

    await pipeline.feed([{"id": "norm", "value": "NormalPrio"}], priority=100)
    print("Fed: Normal priority (100)")

    await pipeline.feed([{"id": "high", "value": "HighPrio"}], priority=10)
    print("Fed: High priority (10)")

    await pipeline.feed([{"id": "crit", "value": "CRITICAL"}], priority=0)
    print("Fed: Critical priority (0)")

    print("\n--- Waiting for processing ---")
    await pipeline.join()

    print()
    print("=" * 60)
    print("Processing Order (tracked via callbacks)")
    print("=" * 60)
    print()

    for idx, item_id in enumerate(processing_order, 1):
        print(f"  {idx}. {item_id}")

    print()
    print("Expected order after blocker:")
    print("  Critical (0) → High (10) → Normal (100) → Low (500)")
    print()

    results = pipeline.results
    print(f"✅ Finished. {len(results)} items processed.")


if __name__ == "__main__":
    asyncio.run(main())
