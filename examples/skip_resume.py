
import asyncio
import random
from dataclasses import dataclass
from antflow import Pipeline, Stage

# --- Simulation Setup ---

@dataclass
class JobItem:
    id: int
    data: str
    dataset_uploaded: bool = False
    model_trained: bool = False
    results_saved: bool = False

async def upload_dataset(item: JobItem):
    print(f"[Upload] Uploading dataset for {item.id}...")
    await asyncio.sleep(0.1)
    item.dataset_uploaded = True
    return item

async def train_model(item: JobItem):
    print(f"[Train ] Training model for {item.id}...")
    await asyncio.sleep(0.1)
    # Simulate random crash during training
    if random.random() < 0.4:
        raise RuntimeError(f"Training crashed for {item.id}!")
    item.model_trained = True
    return item

async def save_results(item: JobItem):
    print(f"[Save  ] Saving results for {item.id}...")
    await asyncio.sleep(0.1)
    item.results_saved = True
    return item

async def main():
    # 1. Define Stages with skip_if conditions
    # This allows us to re-run the pipeline safely!
    
    stage_upload = Stage(
        "Upload", 
        workers=2, 
        tasks=[upload_dataset],
        # Skip if dataset already uploaded
        skip_if=lambda item: item.dataset_uploaded
    )
    
    stage_train = Stage(
        "Train", 
        workers=2, 
        tasks=[train_model],
        retry="per_task", task_attempts=1, # Fail fast for demo
        # Skip if model already trained
        skip_if=lambda item: item.model_trained
    )
    
    stage_save = Stage(
        "Save", 
        workers=2, 
        tasks=[save_results],
        # Skip if results already saved
        skip_if=lambda item: item.results_saved
    )

    pipeline = Pipeline([stage_upload, stage_train, stage_save])

    # 2. create initial jobs
    jobs = [JobItem(id=i, data=f"job_{i}") for i in range(5)]

    print("--- RUN 1: Starts from scratch (Some will fail) ---")
    try:
        # We expect some failures due to random crash
        results = await pipeline.run(jobs)
    except Exception:
        pass # Pipeline might raise if all fail, or we just look at results
    
    print(f"\nStats Run 1: {pipeline.get_stats()}")
    
    # Let's see the state of our objects
    print("\nJob Status after Run 1:")
    for job in jobs:
        status = []
        if job.dataset_uploaded: status.append("Uploaded")
        if job.model_trained: status.append("Trained")
        if job.results_saved: status.append("Saved")
        print(f"Job {job.id}: {', '.join(status)}")

    print("\n--- RUN 2: Retry same objects (Smart Resume) ---")
    print("Notice that 'Upload' and successful 'Train' steps are SKIPPED!")
    
    # We feed the EXACT SAME objects again. 
    # Because they hold their state, stages will auto-skip!
    results_2 = await pipeline.run(jobs)
    
    print(f"\nStats Run 2: {pipeline.get_stats()}")
    print("\nFinal Job Status:")
    for job in results_2:
        # Results might be wrapped or original depending on pipeline config
        # Default run returns PipelineResult objects
        val = job.value
        status = []
        if val.dataset_uploaded: status.append("Uploaded")
        if val.model_trained: status.append("Trained")
        if val.results_saved: status.append("Saved")
        print(f"Job {val.id}: {', '.join(status)}")

if __name__ == "__main__":
    asyncio.run(main())
