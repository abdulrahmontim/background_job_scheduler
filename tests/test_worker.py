import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.job import Job
from app.scheduler.heap import MinHeap
from app.scheduler.manager import JobPoller


@pytest_asyncio.fixture
async def seed_test_jobs(setup_database):
    """
    Setup: Injects test jobs into the DB.
    Teardown: Deletes them after the test finishes.
    """
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        
        # 1. Define the specific edge cases
        test_jobs = [
            Job(type="test_A", priority=1, effective_priority=1, scheduled_at=now - timedelta(minutes=10), payload={"name": "A"}),
            Job(type="test_B", priority=1, effective_priority=1, scheduled_at=now - timedelta(minutes=5), payload={"name": "B"}),
            Job(type="test_C", priority=3, effective_priority=3, scheduled_at=now - timedelta(minutes=20), payload={"name": "C"}),
            Job(type="test_D", priority=2, effective_priority=2, scheduled_at=now, payload={"name": "D"}),
            Job(type="test_E", priority=1, effective_priority=1, scheduled_at=now + timedelta(hours=2), payload={"name": "E"}),
        ]
        
        # 2. Insert into the database
        session.add_all(test_jobs)
        await session.commit()
        
        # 3. Yield passes the list of jobs to the test function
        yield test_jobs
        
        # 4. TEARDOWN: Clean up the database after the test
        test_job_ids = [job.id for job in test_jobs]
        await session.execute(delete(Job).where(Job.id.in_(test_job_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_heap_sorting_and_staging_loader(seed_test_jobs):
    """Verifies that the JobPoller correctly fetches and sorts jobs by the 3-tier tuple constraint."""
    
    # 1. Initialize the architecture
    heap = MinHeap()
    loader = JobPoller(heap)
    
    # 2. Trigger one cycle of the background worker
    await loader._fetch_and_load_jobs()
    
    # 3. Pop everything out of the heap
    popped_jobs = []
    while len(heap) > 0:
        node = heap.pop()
        if node is not None:
            popped_jobs.append(node)
            
    # 4. Filter the heap results to ONLY look at the 5 jobs we just inserted.
    # (This makes the test robust, even if you have 100 old jobs lingering in the DB)
    test_job_ids = [job.id for job in seed_test_jobs]
    our_popped_jobs = [node for node in popped_jobs if node.job_id in test_job_ids]
    
    # --- STRICT ASSERTIONS ---
    
    # Assert 1: Only 4 jobs were loaded (Job E is in the future)
    assert len(our_popped_jobs) == 4
    
    # Assert 2: Verify the mathematical execution order
    assert our_popped_jobs[0].job_id == seed_test_jobs[0].id  # 1st: Job A (Pri 1, 10 mins ago)
    assert our_popped_jobs[1].job_id == seed_test_jobs[1].id  # 2nd: Job B (Pri 1, 5 mins ago)
    assert our_popped_jobs[2].job_id == seed_test_jobs[3].id  # 3rd: Job D (Pri 2, Now)
    assert our_popped_jobs[3].job_id == seed_test_jobs[2].id  # 4th: Job C (Pri 3, 20 mins ago)
    
    # Assert 3: Guarantee Job E was entirely ignored
    job_e_id = seed_test_jobs[4].id
    assert not any(node.job_id == job_e_id for node in popped_jobs)