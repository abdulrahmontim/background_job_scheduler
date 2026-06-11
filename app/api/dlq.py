from fastapi import APIRouter

router = APIRouter()



@router.get("")
async def list_dlq():
    ...
    

@router.post("/{job_id}/retry")
async def retry_dlq_job():
    ...