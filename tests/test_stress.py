import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from app.models.job import Job, JobStatus
from app.database import AsyncSessionLocal # Ensure you have your session factory imported

async def inject_load():
    async with AsyncSessionLocal() as session:
        jobs = []
        for i in range(20):
            # Mix of immediate jobs and delayed jobs
            scheduled_offset = i * 2  # Each job scheduled 2 seconds apart
            job = Job(
                id=str(uuid.uuid4()),
                type="email",
                payload={"email": f"test_{i}@example.com"},
                status=JobStatus.PENDING,
                scheduled_at=datetime.now(timezone.utc) + timedelta(seconds=scheduled_offset)
            )
            jobs.append(job)
        
        session.add_all(jobs)
        await session.commit()
        print(f"🚀 Injected 20 jobs into the database.")

if __name__ == "__main__":
    asyncio.run(inject_load())