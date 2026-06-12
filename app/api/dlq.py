import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Assuming you have a get_db dependency in app.dependencies or app.database
from app.database import AsyncSessionLocal
from app.models.dlq import DeadLetterJob
from app.models.job import Job, JobStatus

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

router = APIRouter()

@router.get("")
async def get_dead_letters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeadLetterJob))
    return result.scalars().all()

@router.post("/{dlq_id}/retry")
async def retry_dead_letter(dlq_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeadLetterJob).where(DeadLetterJob.id == dlq_id))
    dlq_entry = result.scalar_one_or_none()
    
    if not dlq_entry:
        raise HTTPException(status_code=404, detail="DLQ entry not found")
        
    resurrected_job = Job(
        id=dlq_entry.original_job_id,
        type=dlq_entry.type,
        payload=dlq_entry.payload,
        status=JobStatus.PENDING,
        scheduled_at=datetime.now(timezone.utc),
        priority=3, 
        effective_priority=3,
        retry_count=0,
        dependencies=[]
    )
    
    db.add(resurrected_job)
    await db.delete(dlq_entry)
    await db.commit()
    
    return {"message": f"Job {dlq_entry.original_job_id} resurrected successfully."}