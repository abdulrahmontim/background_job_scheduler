import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from random import randint, uniform

from app.database import AsyncSessionLocal
from app.models.dlq import DeadLetterJob
from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap
from app.handlers.email_handler import process_email_job
from app.scheduler.heap import JobNode

import os

logger = logging.getLogger(__name__)


class WorkerEngine:
    def __init__(self, heap: MinHeap):
        
        self.poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", 3.0))
        self.max_retries = int(os.getenv("MAX_RETRIES", 3))
        self.concurrency_limit = int(os.getenv("CONCURRENCY_LIMIT", 10))
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)
        
        self.heap = MinHeap()
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info("Worker Execution Engine starting... listening for jobs.")
        
        try:
            while self.is_running:
                if not self.heap.is_empty():
                    node = self.heap.pop()
                    if node is not None:
                        await self._process_job(node.job_id)
                else:
                    await self._poll_database()
                    await asyncio.sleep(self.poll_interval)
                    
        except asyncio.CancelledError:
            logger.info("Shutdown signal received. Stopping worker gracefully...")
        finally:
            self.is_running = False
            logger.info("Worker stopped.")
            
    async def stop(self):
        self.is_running = False
        logger.info("Worker Execution Engine stopping.")

    async def _process_job(self, job_id):
        async with AsyncSessionLocal() as session:
            query = select(Job).where(
                Job.id == job_id
            ).with_for_update(skip_locked=True)
            
            result = await session.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                return
                
            try:
                if job.type == "email":
                    await process_email_job(job.id, job.payload)
                else:
                    logger.warning(f"Unknown job type: {job.type}")
                    
                job.status = JobStatus.COMPLETED
                job.error_message = ""
                
                if job.interval:
                    new_scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=job.interval)
                    
                    recurring_job = Job(
                        type=job.type,
                        payload=job.payload,
                        priority=job.priority,
                        effective_priority=job.priority,
                        interval=job.interval,
                        scheduled_at=new_scheduled_time,
                        status=JobStatus.PENDING
                    )
                    session.add(recurring_job)
                    logger.info(f"🔁 Spawning recurring clone for Job {job.id}. Next run: {new_scheduled_time}")
                    
            except Exception as e:
                job.retry_count += 1
                job.error_message = str(e)
                
                if job.retry_count < 3:
                    delay = 2 ** job.retry_count
                    backoff = delay * uniform(0.8, 1.2)                    
                    
                    job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                    job.status = JobStatus.PENDING
                    
                    logger.warning(f"⚠️ Job {job.id} failed. Retrying in {backoff}s (Attempt {job.retry_count}/3)")
                else:
                    job.status = JobStatus.FAILED
                    logger.error(f"❌ Job {job.id} permanently failed (Attempt 3/3). Routing to DLQ.")
                    
                    dlq = DeadLetterJob(
                        original_job_id=job.id,
                        type=job.type,
                        payload=job.payload,
                        error_message=job.error_message
                    )
                    session.add(dlq)
                    
            finally:
                await session.commit()
                
    
    async def _poll_database(self):
        """Sweeps the database for due jobs and loads them into the heap."""
        async with AsyncSessionLocal() as session:
            # Find all PENDING jobs where the scheduled time is NOW or in the past
            query = select(Job).where(
                Job.status == JobStatus.PENDING,
                Job.scheduled_at <= datetime.now(timezone.utc)
            )
            result = await session.execute(query)
            due_jobs = result.scalars().all()

            # Push them into your heap (Adjust this line to match your exact Heap Node structure)
            for job in due_jobs:
                node = JobNode(effective_priority=job.effective_priority, job_id=job.id, scheduled_at=job.scheduled_at)
                self.heap.push(node)

            if due_jobs:
                logger.info(f"Loaded {len(due_jobs)} new jobs into the MinHeap")