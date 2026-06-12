import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.models.dlq import DeadLetterJob

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

async def replay_all_dlq_jobs():
    print("\n--- Initiating DLQ Replay ---")
    async with AsyncSessionLocal() as session:
        # 1. Grab everything currently sitting in the DLQ
        result = await session.execute(select(DeadLetterJob))
        dlq_records = result.scalars().all()
        
        if not dlq_records:
            logger.info("📭 The Dead Letter Queue is empty. Nothing to replay.")
            return
            
        replayed_count = 0
        for dlq in dlq_records:
            # 2. Find the original FAILED job in the main jobs table
            job_result = await session.execute(
                select(Job).where(Job.id == dlq.original_job_id)
            )
            original_job = job_result.scalar_one_or_none()
            
            if original_job:
                # 3. Resurrect it: Reset status, zero out retries, and schedule for NOW
                original_job.status = JobStatus.PENDING
                original_job.retry_count = 0
                original_job.error_message = ""
                original_job.scheduled_at = datetime.now(timezone.utc)
                
                # 4. Delete the tombstone record from the DLQ ledger
                await session.delete(dlq)
                replayed_count += 1
                logger.info(f"♻️ Resurrected Job: {original_job.id}")
                
        # 5. Commit all resurrections and deletions atomically
        await session.commit()
        logger.info(f"✅ Successfully replayed {replayed_count} jobs. They are waiting for the worker.")

if __name__ == "__main__":
    asyncio.run(replay_all_dlq_jobs())