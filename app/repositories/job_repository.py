from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import json
import structlog

from sqlalchemy import select, update, delete, and_, or_

from app.models.job import Job, JobStatus
from app.models.dlq import DeadLetterJob

from datetime import datetime, timezone, timedelta


class JobQuery:

    def __init__(self, db: AsyncSession):
        self.db = db


    async def create_job(
        self, job: Job
    ) -> Job:
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job


    async def get_job_by_id(self, job_id: UUID):
        job = await self.db.get(Job, job_id)
        if job and isinstance(job.payload, str):
            try:
                job.payload = json.loads(job.payload)
            except Exception as e:
                structlog.get_logger(__name__).exception("Something went wrong, couldn't load job. Error: {e}")
        return job


    async def list_jobs(
        self,
        type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ):
        query = select(Job)
        
        if type:
            query = query.where(Job.type == type)
        
        if status:
            try:
                enum_status = JobStatus(status)
                query = query.where(Job.status == enum_status)
            except ValueError:
                return []
        
        if priority:
            query = query.where(Job.priority == priority)
            
        query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        jobs = result.scalars().all()
        for j in jobs:
            if isinstance(j.payload, str):
                try:
                    j.payload = json.loads(j.payload)
                except Exception:
                    pass
        return jobs

    async def delete_job(self, job_id: UUID):
        job = await self.get_job_by_id(job_id)
        if not job:
            return None
        
        await self.db.delete(job)
        await self.db.commit()

    async def cancel_job(self, job_id: UUID):
        job = await self.get_job_by_id(job_id)
        if not job:
            return None
        
        job.status = JobStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(job)
        return await self.db.get(Job, job_id)

    async def update_job_status(self, job_id: UUID, status: JobStatus):
        job = await self.get_job_by_id(job_id)
        if not job:
            return None
        
        job.status = status
        await self.db.commit()
        await self.db.refresh(job)
    
    
    async def get_pending_due_jobs(self, limit: int = 50):
        now = datetime.now(timezone.utc)
        query = select(Job).where(
            Job.status == JobStatus.PENDING,
            Job.scheduled_at <= now
        ).limit(limit)
        
        result = await self.db.execute(query)
        jobs = result.scalars().all()
        for j in jobs:
            if isinstance(j.payload, str):
                try:
                    j.payload = json.loads(j.payload)
                except Exception:
                    pass
        return jobs