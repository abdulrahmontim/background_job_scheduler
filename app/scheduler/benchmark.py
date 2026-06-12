import time
import random
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.scheduler.heap import MinHeap, JobNode as HeapNode
from app.scheduler.timing_wheel import TimingWheel, WheelNode

def run_benchmark():
    NUM_JOBS = 10_000
    print(f"--- Running Benchmark: Min-Heap vs Timing Wheel ({NUM_JOBS} Jobs) ---")
    
    # --- 1. Min-Heap Benchmark ---
    heap = MinHeap()
    now = datetime.now(timezone.utc)
    
    # Generate 10,000 jobs with random priorities and times
    heap_jobs = [
        HeapNode(
            job_id=uuid4(),
            effective_priority=random.randint(1, 3),
            scheduled_at=now + timedelta(seconds=random.randint(1, 300))
        ) for _ in range(NUM_JOBS)
    ]
    
    # Time the Insertions
    start_time = time.perf_counter()
    for job in heap_jobs:
        heap.push(job)
    heap_insert_time = time.perf_counter() - start_time
    
    # Time the Extractions
    start_time = time.perf_counter()
    while len(heap) > 0:
        heap.pop()
    heap_extract_time = time.perf_counter() - start_time
    
    print(f"\n[Min-Heap - O(log n)]")
    print(f"  Insert:  {heap_insert_time:.5f} seconds")
    print(f"  Extract: {heap_extract_time:.5f} seconds")
    
    # --- 2. Timing Wheel Benchmark ---
    wheel = TimingWheel(slots=600)
    
    # Generate 10,000 jobs with random future delays (1 to 300 seconds)
    wheel_jobs = [
        (WheelNode(job_id=uuid4()), random.randint(1, 300)) 
        for _ in range(NUM_JOBS)
    ]
    
    # Time the Insertions
    start_time = time.perf_counter()
    for job, delay in wheel_jobs:
        wheel.schedule(job, delay)
    wheel_insert_time = time.perf_counter() - start_time
    
    # Time the Extractions (We simulate 300 seconds passing)
    start_time = time.perf_counter()
    for _ in range(300):
        wheel.tick()
    wheel_extract_time = time.perf_counter() - start_time
    
    print(f"\n[Timing Wheel - O(1)]")
    print(f"  Insert:  {wheel_insert_time:.5f} seconds")
    print(f"  Extract: {wheel_extract_time:.5f} seconds")
    
if __name__ == "__main__":
    run_benchmark()