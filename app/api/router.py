from fastapi import APIRouter
from app.api import jobs, dlq, sse

router = APIRouter()

router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(dlq.router, prefix="/dlq", tags=["dlq"])
router.include_router(sse.router, prefix="/sse", tags=["sse"])