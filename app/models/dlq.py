from sqlalchemy import JSON, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7

from app.database import Base

class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True, default=uuid7)
    
    # fk?
    original_job_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)