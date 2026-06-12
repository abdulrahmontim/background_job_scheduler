import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.job import Job

router = APIRouter()

async def fetch_job_metrics():
    async with AsyncSessionLocal() as session:
        query = select(Job.status, func.count(Job.id)).group_by(Job.status)
        result = await session.execute(query)
        counts = {status.name: count for status, count in result.all()}
        statuses = ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"]
        return {s: counts.get(s, 0) for s in statuses}

async def metric_generator():
    while True:
        try:
            metrics = await fetch_job_metrics()
            yield f"data: {json.dumps(metrics)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        await asyncio.sleep(2)

@router.get("/stream")
async def event_stream():
    return StreamingResponse(metric_generator(), media_type="text/event-stream")