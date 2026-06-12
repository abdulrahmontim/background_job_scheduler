import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap, JobNode

logger = logging.getLogger(__name__)


class JobPoller:
    def __init__(self, heap: MinHeap, poll_interval: int = 5):
        self.heap = heap
        self.poll_interval = poll_interval
        self.is_running = False
        
    async def start(self):
        try:
            await self._fetch_and_load_jobs()
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}")
            
        await asyncio.sleep(self.poll_interval)
        
    async def stop(self):
        self.is_running = False
        logger.info("Job Poller Engine stopped")
        
    async def _is_topologically_ready(self, session, job: Job) -> bool:
        """Evaluates dependencies. Returns True ONLY if all parent jobs are COMPLETED."""
        if not job.dependencies:
            return True
            
        deps = job.dependencies
        
        # 1. Parse JSON if it's stored as a string
        if isinstance(deps, str):
            import json
            try:
                deps = json.loads(deps)
            except json.JSONDecodeError:
                return True
                
        if not deps:
            return True

        # 2. Force convert EVERY item into a real uuid.UUID object
        import uuid
        parsed_deps = []
        for d in deps:
            if isinstance(d, uuid.UUID):
                parsed_deps.append(d)
            else:
                try:
                    # Cast to string first to safely handle ints or malformed types
                    parsed_deps.append(uuid.UUID(str(d)))
                except ValueError:
                    continue # Ignore invalid UUIDs

        if not parsed_deps:
            return True

        # 3. CRITICAL FIX: Pass `parsed_deps` to the in_() clause, NOT `deps`
        query = select(Job.id).where(
            Job.id.in_(parsed_deps),
            Job.status != JobStatus.COMPLETED
        )
        
        result = await session.execute(query)
        blocking_parents = result.scalars().all()

        return len(blocking_parents) == 0

    async def _fetch_and_load_jobs(self):
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)

            query = select(Job).where(
                Job.status == JobStatus.PENDING,
                Job.scheduled_at <= now
            ).with_for_update(skip_locked=True)
            
            result = await session.execute(query)
            jobs = result.scalars().all()
            
            if not jobs:
                return
            
            loaded_count = 0
            for job in jobs:
                # PHASE 5.2: DAG Gatekeeper check
                if not await self._is_topologically_ready(session, job):
                    continue  # Skip this job, let it stay PENDING

                job.status = JobStatus.PROCESSING
                
                node = JobNode(
                    job_id=job.id,
                    effective_priority=job.effective_priority,
                    scheduled_at=job.scheduled_at
                )
                self.heap.push(node)
                loaded_count += 1
                
            await session.commit()
            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} jobs into the MinHeap")