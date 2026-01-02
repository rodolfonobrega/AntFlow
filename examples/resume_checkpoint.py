"""
Checkpoint-based resume example.

Demonstrates how to implement a checkpoint system for pipeline recovery:
- Track completed stages per item using StatusTracker callbacks
- On failure, determine which items need to resume from which stage
- Use feed() with target_stage to inject items mid-pipeline

This pattern is useful for:
- Long-running pipelines that may be interrupted
- Exactly-once processing guarantees
- Recovering from crashes without reprocessing completed work
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Dict, List

from antflow import Pipeline, Stage, StatusTracker


async def fetch_data(item_id):
    """Stage 1: Simulate fetching data."""
    await asyncio.sleep(0.1)
    return {"id": item_id, "raw": f"data_{item_id}"}

async def process_data(data):
    """Stage 2: Simulate expensive processing."""
    await asyncio.sleep(0.1)
    # Simulate a random crash if we haven't recovered yet
    if not data.get("recovered", False) and random.random() < 0.3:
         raise RuntimeError(f"Random crash processing {data['id']}!")

    data["processed"] = True
    return data

async def save_data(data):
    """Stage 3: Save results."""
    await asyncio.sleep(0.1)
    data["saved"] = True
    return data

# =============================================================================
# 2. Checkpoint System (Simple In-Memory Simulation)
# =============================================================================

@dataclass
class Checkpoint:
    """Tracks the last successful stage for each item."""
    item_states: Dict[str, str] # item_id -> last_completed_stage_name

class CheckpointManager:
    def __init__(self):
        self.db = Checkpoint({})

    def mark_complete(self, item_id, stage_name):
        """Update item progress."""
        self.db.item_states[str(item_id)] = stage_name
        print(f"[Checkpoint] Item {item_id} completed {stage_name}")

    def get_pending_items(self, all_item_ids: List[int], stages: List[str]) -> Dict[str, List[int]]:
        """
        Determine which stage each item needs to enter next.
        Returns: {target_stage_name: [list_of_items]}
        """
        injections = {}

        for item_id in all_item_ids:
            sid = str(item_id)
            last_stage = self.db.item_states.get(sid)

            if last_stage is None:
                # Not started, go to first stage
                target = stages[0]
            elif last_stage == stages[-1]:
                # Already fully done
                continue
            else:
                # Completed 'last_stage', needs to go to next one
                try:
                    current_idx = stages.index(last_stage)
                    target = stages[current_idx + 1]
                except (ValueError, IndexError):
                    print(f"Unknown stage {last_stage}, restarting.")
                    target = stages[0]

            if target not in injections:
                injections[target] = []
            injections[target].append(item_id)

        return injections

# Global checkpoint manager
ckpt = CheckpointManager()

# =============================================================================
# 3. Pipeline Configuration
# =============================================================================

async def on_status_change(event):
    if event.status == "completed":
        # When a stage completes, checkpoint it!
        # Note: In real apps, payload is in event.metadata or we track via IDs
        ckpt.mark_complete(event.item_id, event.stage)
    elif event.status == "failed":
        print(f"[Monitor] Item {event.item_id} FAILED in {event.stage}: {event.metadata.get('error')}")

async def run_pipeline(items_to_inject: Dict[str, List[Any]]):
    """
    Runs the pipeline, injecting items into specific stages.
    items_to_inject: { "StageName": [items...] }
    """
    tracker = StatusTracker(on_status_change=on_status_change)

    stage1 = Stage("Fetch", 2, [fetch_data])
    stage2 = Stage("Process", 2, [process_data], retry="per_task", task_attempts=1) # 1 attempt to force fail
    stage3 = Stage("Save", 2, [save_data])

    pipeline = Pipeline([stage1, stage2, stage3], status_tracker=tracker)

    print("\n--- Starting Pipeline Run ---")
    await pipeline.start()

    # Inject items into their respective stages
    for stage_name, items in items_to_inject.items():
        if not items:
            continue
        print(f"Injecting {len(items)} items into '{stage_name}'")

        # NOTE: For this example, we need to reconstruct the payload if we are injecting
        # mid-stream. In a real app, you'd load the partial state from DB.
        # Here we just pass the ID and let the tasks handle it (or mock the data).
        prepared_items = []
        for i in items:
            if stage_name == "Fetch":
                prepared_items.append(i) # Raw ID
            else:
                # Recovering state: We fake the data that previous stages would have produced
                # In production, you would fetch this from your database
                prepared_items.append({"id": i, "raw": f"data_{i}", "recovered": True})

        await pipeline.feed(prepared_items, target_stage=stage_name)

    await pipeline.join()
    print("--- Run Complete ---\n")
    return pipeline.results

# =============================================================================
# 4. Main Simulation
# =============================================================================

async def main():
    all_items = list(range(10)) # IDs 0-9
    stages = ["Fetch", "Process", "Save"]

    # --- Run 1: specific items will likely fail due to random crash logic ---
    print(">>> RUN 1: Potential Crashes <<<")
    # Initially, all items go to first stage
    initial_injection = {"Fetch": all_items}
    await run_pipeline(initial_injection)

    # --- Determine what failed / is pending ---
    print("\n>>> DETERMINING RESUME STATE <<<")
    injections = ckpt.get_pending_items(all_items, stages)

    if not injections:
        print("Everything finished successfully! No resume needed.")
        return

    print("Pending work detected:")
    for stage, items in injections.items():
        print(f"  Stage '{stage}': {items}")

    # --- Run 2: Resume from checkpoints ---
    print("\n>>> RUN 2: Resuming Pipeline <<<")
    # This time we inject specifically where they left off
    # 'recovered=True' flag in run_pipeline prevents them from crashing again
    await run_pipeline(injections)

if __name__ == "__main__":
    # Ensure fully clean run
    asyncio.run(main())
