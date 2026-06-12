import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy import update

from typing import cast
from sqlalchemy.engine import CursorResult
from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus

logger = structlog.get_logger(__name__)

async def starvation_daemon():
    """
    Background ticker that runs continuously to monitor for starved jobs.
    """
    threshold_seconds = 900  # 15 minutes threshold
    check_interval = 60      # Run every 60 seconds
    
    logger.info("Starvation daemon initialized.")
    
    while True:
        await asyncio.sleep(check_interval)
        try:
            async with AsyncSessionLocal() as session:
                threshold_time = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
                
                # Atomic update: Decrease effective_priority (higher priority), bounded at 1
                stmt = (
                    update(Job)
                    .where(Job.status == JobStatus.PENDING)
                    .where(Job.scheduled_at <= threshold_time)
                    .where(Job.effective_priority > 1)
                    .values(effective_priority=Job.effective_priority - 1)
                )
                
                raw_result = await session.execute(stmt)
                await session.commit()
                
                result = cast(CursorResult, raw_result)
                
                if result.rowcount > 0: #type: ignore
                    logger.info(f"Starvation Engine: Upgraded priority of {result.rowcount} starving jobs.") #type: ignore
        except Exception as e:
            logger.error(f"Starvation daemon encountered an exception: {e}")