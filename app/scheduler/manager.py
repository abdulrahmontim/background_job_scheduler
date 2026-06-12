import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap, JobNode

logger = logging.getLogger(__name__)


#check every 5s and sleep if job not available
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
            
            for job in jobs:
                job.status = JobStatus.PROCESSING
                
                node = JobNode(
                    job_id=job.id,
                    effective_priority=job.effective_priority,
                    scheduled_at=job.scheduled_at
                )
                self.heap.push(node)
                
            await session.commit()
            logger.info(f"Loaded {len(jobs)} jobs into the MinHeap")
        