import asyncio
import logging
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from app.database import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.scheduler.heap import MinHeap
from app.scheduler.manager import JobPoller
from app.worker.worker import WorkerEngine
from app.config import get_settings


logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO, 
    format="\n[%(levelname)s] %(asctime)s | %(message)s",
    datefmt="%I:%M:%S %p"
)

async def seed_test_jobs(count: int = 5):
    """Injects fresh PENDING email jobs into the database."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        jobs = [
            Job(
                type="email",
                payload={"email": f"engineer_{i}@example.com", "subject": f"Concurrent Load Test {i}"},
                priority=2,
                effective_priority=2,
                scheduled_at=now,
                status=JobStatus.PENDING,
                retry_count=0
            ) for i in range(count)
        ]
        session.add_all(jobs)
        await session.commit()
        logging.info(f"✅ Seeded {count} test email jobs into the database.")

async def main():
    print("\n--- Booting Execution Pipeline ---")
    
    # 1. Seed the database with some jobs to process
    await seed_test_jobs(5)

    # 2. Initialize the shared memory architecture
    heap = MinHeap()
    
    # 3. Boot the Producer (polls DB every 3 seconds) and Consumer
    loader = JobPoller(heap, poll_interval=3)
    worker = WorkerEngine(heap)

    # 4. Run both infinite loops side-by-side
    # This simulates a real production worker environment
    try:
        await asyncio.gather(
            loader.start(),
            worker.start()
        )
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Pipeline shut down by user (Ctrl+C).")