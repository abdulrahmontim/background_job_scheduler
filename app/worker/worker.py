import asyncio
import structlog
import json
import uuid
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from random import uniform

from app.database import AsyncSessionLocal
from app.models.dlq import DeadLetterJob
from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap, JobNode
from app.handlers.email_handler import process_email_job
from app.worker.starvation import starvation_daemon
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

class WorkerEngine:
    def __init__(self, heap: MinHeap):
        self.poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", 3.0))
        self.max_retries = int(os.getenv("MAX_RETRIES", 3))
        self.concurrency_limit = int(os.getenv("CONCURRENCY_LIMIT", 10))
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)
        
        self.heap = heap
        self.is_running = False
        self._daemon_task = None

    async def start(self):
        self.is_running = True
        logger.info("Worker Execution Engine starting... listening for jobs.")
        
        # PHASE 5.1: Boot the Starvation Daemon
        self._daemon_task = asyncio.create_task(starvation_daemon())
        
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
            if self._daemon_task:
                self._daemon_task.cancel()
            logger.info("Worker stopped.")
            
    async def stop(self):
        self.is_running = False
        if self._daemon_task:
            self._daemon_task.cancel()
        logger.info("Worker Execution Engine stopping.")

    async def _is_topologically_ready(self, session, job: Job) -> bool:
        """Phase 5.2: Evaluates dependencies before pushing to heap."""
        if not job.dependencies:
            return True
            
        deps = job.dependencies
        
        # 1. Parse JSON if it's stored as a string
        if isinstance(deps, str):
            try:
                deps = json.loads(deps)
            except json.JSONDecodeError:
                return True
                
        if not deps:
            return True

        # 2. Force convert EVERY item into a real uuid.UUID object
        parsed_deps = []
        for d in deps:
            if isinstance(d, uuid.UUID):
                parsed_deps.append(d)
            else:
                try:
                    parsed_deps.append(uuid.UUID(str(d)))
                except ValueError:
                    continue

        if not parsed_deps:
            return True

        # 3. Query using the properly typed UUID objects
        query = select(Job.id).where(
            Job.id.in_(parsed_deps),
            Job.status != JobStatus.COMPLETED
        )
        
        result = await session.execute(query)
        blocking_parents = result.scalars().all()

        return len(blocking_parents) == 0

    async def _process_job(self, job_id):
        async with AsyncSessionLocal() as session:
            query = select(Job).where(
                Job.id == job_id
            ).with_for_update(skip_locked=True)
            
            result = await session.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                return

            if job.status == JobStatus.CANCELLED:
                logger.info(f"Job {job.id} was cancelled. Skipping.")
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
                        id=uuid.uuid4(),
                        type=job.type,
                        payload=job.payload,
                        priority=job.priority,
                        effective_priority=job.priority,
                        interval=job.interval,
                        scheduled_at=new_scheduled_time,
                        status=JobStatus.PENDING,
                        dependencies=[]
                    )
                    session.add(recurring_job)
                    logger.info(f"Recurring clone for Job {job.id} scheduled next at {new_scheduled_time}")
                    
            except Exception as e:
                job.retry_count += 1
                job.error_message = str(e)

                backoff_seconds = [1, 5, 25]
                idx = min(job.retry_count - 1, 2)
                delay = backoff_seconds[idx]
                backoff = delay * uniform(0.8, 1.2)
                
                if job.retry_count < 3:
                    job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                    job.status = JobStatus.PENDING
                    
                    logger.warning(f"Job {job.id} failed. Retrying in {backoff:.2f}s (Attempt {job.retry_count}/3)")
                else:
                    job.status = JobStatus.FAILED
                    logger.error(f"Job {job.id} permanently failed (Attempt 3/3). Routing to DLQ.")
                    
                    dlq = DeadLetterJob(
                        id=uuid.uuid4(),
                        original_job_id=job.id,
                        type=job.type,
                        payload=job.payload,
                        error_message=job.error_message
                    )
                    session.add(dlq)

                    dlq_count = await session.scalar(select(func.count(DeadLetterJob.id)))
                    if dlq_count and dlq_count >= settings.DLQ_ALERT_THRESHOLD:
                        logger.warning(f"DLQ threshold reached: {dlq_count} items (threshold={settings.DLQ_ALERT_THRESHOLD}). Alert sent to {settings.ALERT_EMAIL}")
                    
            finally:
                await session.commit()
                
    async def _poll_database(self):
        """Sweeps the database for due jobs and loads them into the heap."""
        async with AsyncSessionLocal() as session:
            query = select(Job).where(
                Job.status == JobStatus.PENDING,
                Job.scheduled_at <= datetime.now(timezone.utc)
            ).with_for_update(skip_locked=True)
            result = await session.execute(query)
            due_jobs = result.scalars().all()

            loaded_count = 0
            for job in due_jobs:
                # PHASE 5.2: DAG Gatekeeper check
                if not await self._is_topologically_ready(session, job):
                    continue

                job.status = JobStatus.PROCESSING
                node = JobNode(effective_priority=job.effective_priority, job_id=job.id, scheduled_at=job.scheduled_at, created_at=job.created_at)
                self.heap.push(node)
                loaded_count += 1

            await session.commit()
            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} new jobs into the MinHeap")