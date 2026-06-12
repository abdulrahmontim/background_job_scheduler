import os
import asyncio
from random import uniform, random
import logging
from app.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

FAILURE_RATE = float(os.getenv("EMAIL_FAILURE_RATE", "0.0"))


async def process_email_job(job_id, payload: dict) -> bool:
    recipient = payload.get("email", "unknown@example.com")
    subject = payload.get("subject", "No Subject")
    
    logger.info(f"[{job_id}] Compiling email for {recipient}...")
    
    friction = uniform(0.5, 2.0) # latency mock
    await asyncio.sleep(friction)
    
    if random() < settings.EMAIL_FAILURE_RATE: # failure mock
        raise ConnectionError(f"Server Timeout: Failed to reach recipient server for {recipient}")
    
    logger.info(f"✅ Successfully dispatched email: '{subject}' to {recipient}")
    return True
    