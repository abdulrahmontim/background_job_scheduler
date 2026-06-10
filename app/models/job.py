from sqlalchemy import JSON, String, Integer, Enum, Text
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

import enum
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7

from app.database import Base


class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(Base):
    __tablename__ = "jobs"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True, default=uuid7)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    interval: Mapped[int] = mapped_column(Integer, nullable=True)
    # interval_str : Mapped[str] = mapped_column(String(20), nullable=True)
    
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    effective_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list,nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    