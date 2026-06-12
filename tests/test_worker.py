import pytest
import pytest_asyncio
import uuid
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete, select, update

from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap
from app.scheduler.manager import JobPoller
from app.worker.worker import WorkerEngine #type: ignore


@pytest_asyncio.fixture
async def seed_test_jobs(db_session):
    """
    Setup: Injects test jobs into the DB using the isolated db_session.
    Teardown: Handled by the fixture yield/rollback.
    """
    now = datetime.now(timezone.utc)
    
    # 1. Define the specific edge cases (Using UUIDs and payload={} to satisfy DB constraints)
    test_jobs = [
        Job(id=uuid.uuid4(), type="test_A", priority=1, effective_priority=1, scheduled_at=now - timedelta(minutes=10), payload={"name": "A"}, dependencies=[]),
        Job(id=uuid.uuid4(), type="test_B", priority=1, effective_priority=1, scheduled_at=now - timedelta(minutes=5), payload={"name": "B"}, dependencies=[]),
        Job(id=uuid.uuid4(), type="test_C", priority=3, effective_priority=3, scheduled_at=now - timedelta(minutes=20), payload={"name": "C"}, dependencies=[]),
        Job(id=uuid.uuid4(), type="test_D", priority=2, effective_priority=2, scheduled_at=now, payload={"name": "D"}, dependencies=[]),
        Job(id=uuid.uuid4(), type="test_E", priority=1, effective_priority=1, scheduled_at=now + timedelta(hours=2), payload={"name": "E"}, dependencies=[]),
    ]
    
    # 2. Insert into the database
    db_session.add_all(test_jobs)
    await db_session.commit()
    
    # 3. Yield passes the list of jobs to the test function
    yield test_jobs
    
    # 4. TEARDOWN: Clean up the database after the test
    test_job_ids = [job.id for job in test_jobs]
    await db_session.execute(delete(Job).where(Job.id.in_(test_job_ids)))
    await db_session.commit()


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


@pytest.mark.asyncio
async def test_dag_dependency_resolver(db_session):
    """
    Phase 5.2: Ensure jobs are blocked if parents are not COMPLETED.
    """
    now = datetime.now(timezone.utc)
    
    id_parent_done = uuid.uuid4()
    id_parent_pending = uuid.uuid4()
    id_child_blocked = uuid.uuid4()
    id_child_ready = uuid.uuid4()

    # 1. SETUP: Create the DAG
    parent_done = Job(id=id_parent_done, type="test", status=JobStatus.COMPLETED, scheduled_at=now, payload={}, dependencies=[])
    parent_pending = Job(id=id_parent_pending, type="test", status=JobStatus.PENDING, scheduled_at=now, payload={}, dependencies=[])
    
    # Child Blocked depends on the PENDING parent
    child_blocked = Job(
        id=id_child_blocked, type="test", status=JobStatus.PENDING, 
        scheduled_at=now, payload={}, 
        dependencies=json.dumps([str(id_parent_pending)]) 
    )
    
    # Child Ready depends on the COMPLETED parent
    child_ready = Job(
        id=id_child_ready, type="test", status=JobStatus.PENDING, 
        scheduled_at=now, payload={}, 
        dependencies=json.dumps([str(id_parent_done)])
    )

    db_session.add_all([parent_done, parent_pending, child_blocked, child_ready])
    await db_session.commit()

    # 2. ACT: Check topological readiness using WorkerEngine logic
    worker = WorkerEngine(MinHeap())
    
    is_blocked_ready = await worker._is_topologically_ready(db_session, child_blocked)
    is_child_ready = await worker._is_topologically_ready(db_session, child_ready)
    is_parent_ready = await worker._is_topologically_ready(db_session, parent_pending)

    # 3. ASSERT: Validate the Gatekeeper logic
    assert is_blocked_ready is False, "Child with pending parent should NOT be ready"
    assert is_child_ready is True, "Child with completed parent SHOULD be ready"
    assert is_parent_ready is True, "Job with no dependencies SHOULD be ready"


@pytest.mark.asyncio
async def test_starvation_engine_logic(db_session):
    """
    Phase 5.1: Ensure old jobs get a priority boost based on the atomic UPDATE logic.
    """
    now = datetime.now(timezone.utc)
    
    # 1. SETUP: Create three jobs
    job_starving = Job(
        id=uuid.uuid4(), type="test", status=JobStatus.PENDING, 
        scheduled_at=now - timedelta(minutes=20), payload={}, dependencies=[],
        priority=3, effective_priority=3
    )
    
    job_max_priority = Job(
        id=uuid.uuid4(), type="test", status=JobStatus.PENDING, 
        scheduled_at=now - timedelta(minutes=20), payload={}, dependencies=[],
        priority=3, effective_priority=1
    )
    
    job_recent = Job(
        id=uuid.uuid4(), type="test", status=JobStatus.PENDING, 
        scheduled_at=now - timedelta(minutes=5), payload={}, dependencies=[],
        priority=3, effective_priority=3
    )

    db_session.add_all([job_starving, job_max_priority, job_recent])
    await db_session.commit()

    # 2. ACT: Execute the Starvation Update Logic
    threshold_time = now - timedelta(seconds=900) # 15 mins
    
    stmt = (
        update(Job)
        .where(Job.status == JobStatus.PENDING)
        .where(Job.scheduled_at <= threshold_time)
        .where(Job.effective_priority > 1)
        .values(effective_priority=Job.effective_priority - 1)
    )
    await db_session.execute(stmt)
    await db_session.commit()

    # 3. ASSERT: Refresh and verify states
    await db_session.refresh(job_starving)
    await db_session.refresh(job_max_priority)
    await db_session.refresh(job_recent)

    assert job_starving.effective_priority == 2, "Starving job should be upgraded from 3 to 2"
    assert job_max_priority.effective_priority == 1, "Max priority job should remain at 1"
    assert job_recent.effective_priority == 3, "Recent job should remain at 3"