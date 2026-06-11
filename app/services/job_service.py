from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

from typing import Optional
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.repositories.job_repository import JobQuery
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate
# from app.repositories.dlq_repository import DLQQuery


class JobService:
    def __init__(self, query: JobQuery):
        self.query = query

    async def create_job(
        self, data: JobCreate
    ):
        job = Job(
            type=data.type,
            payload=data.payload,
            scheduled_at=data.scheduled_at,
            interval=data.interval,
            priority=data.priority,
            dependencies=data.dependencies or [],
        )
        
        created_job = await self.query.create_job(job)
        return created_job
    

    async def list_jobs(self):
        response = await self.query.list_jobs()
        return response
    
    
    async def get_job_by_id(self, job_id: UUID):
        response = await self.query.get_job_by_id(job_id)
        return response
    
    
    async def cancel_job(self, job_id: UUID):
        return await self.query.cancel_job(job_id)
        

    async def get_pending_due_jobs(self):
        return await self.query.get_pending_due_jobs()


