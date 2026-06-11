from pydantic import BaseModel, Field
from typing import Optional

from app.models.job import JobStatus
from datetime import datetime
from uuid import UUID


class JobCreate(BaseModel):
    type: str
    payload: dict
    priority: int = Field(default=3, ge=1, le=3)
    scheduled_at: datetime
    interval: Optional[int] = None
    dependencies: list[str] = []

    model_config = {"extra": "forbid"}

class JobResponse(BaseModel):
    id: UUID
    type: str
    status: JobStatus
    payload: dict
    priority: int
    effective_priority: int
    scheduled_at: datetime
    created_at: datetime
    retry_count: int
    interval: Optional[int] = None
    dependencies: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}