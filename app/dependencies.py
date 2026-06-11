from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.job_repository import JobQuery
from app.services.job_service import JobService


async def get_job_query(db: AsyncSession = Depends(get_db)):
    return JobQuery(db)

async def get_job_service(query: JobQuery = Depends(get_job_query)) -> JobService:
    return JobService(query)