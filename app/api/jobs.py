from fastapi import APIRouter, Depends, status, HTTPException
from uuid import UUID

from app.dependencies import get_job_service
from app.schemas.job import JobCreate, JobResponse
from app.services.job_service import JobService

router = APIRouter()

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(data: JobCreate, service: JobService = Depends(get_job_service)):
    return await service.create_job(data)

@router.get("", response_model=list[JobResponse])
async def list_jobs(service: JobService = Depends(get_job_service)):
    return await service.list_jobs()

@router.get("/pending/due", response_model=list[JobResponse])
async def get_pending_due_jobs(service: JobService = Depends(get_job_service)):
    return await service.get_pending_due_jobs()

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, service: JobService = Depends(get_job_service)):
    job = await service.get_job_by_id(job_id)
    if not job:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job

@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: UUID, service: JobService = Depends(get_job_service)):
    try:
        job = await service.cancel_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))