
import asyncio

import pytest

from antflow import Pipeline, Stage, StatusTracker


async def add_suffix(text):
    return text + "_processed"

@pytest.mark.asyncio
async def test_skip_if_behavior():
    """Verify that stage is skipped when predicate is true."""

    # Condition: skip if item already ends with "_processed"
    def is_already_done(item):
        return isinstance(item, str) and item.endswith("_processed")

    stage = Stage("Transform", 1, [add_suffix], skip_if=is_already_done)

    # We use a tracker to verify "skipped" status
    tracker = StatusTracker()
    pipeline = Pipeline([stage], status_tracker=tracker)

    await pipeline.start()

    # Feed items
    # 1. New item: "raw" -> should process -> "raw_processed"
    await pipeline.feed(["raw"], priority=10)

    # 2. Done item: "data_processed" -> should skip -> "data_processed" (pass-through)
    await pipeline.feed(["data_processed"], priority=10)

    await pipeline.join()

    results = pipeline.results
    values = [r.value for r in results]

    # Check values
    assert "raw_processed" in values
    assert "data_processed" in values

    # Check statuses
    # We need to find the event for "data_processed"
    # The IDs are assigned sequentially. "raw" = 0, "data_processed" = 1

    # Check item 0
    history_0 = tracker.get_history(0)
    statuses_0 = [e.status for e in history_0]
    assert "in_progress" in statuses_0
    assert "completed" in statuses_0
    assert "skipped" not in statuses_0

    # Check item 1
    history_1 = tracker.get_history(1)
    statuses_1 = [e.status for e in history_1]
    assert "skipped" in statuses_1
    assert "in_progress" not in statuses_1
    assert "completed" not in statuses_1

    print("Skip tests passed!")

if __name__ == "__main__":
    asyncio.run(test_skip_if_behavior())
