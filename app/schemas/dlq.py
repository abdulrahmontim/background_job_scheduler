from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class DLQResponse(BaseModel):
    id: UUID
    original_job_id: UUID
    type: str
    payload: dict
    failed_at: datetime
    error_message: str | None = None

    model_config = {"from_attributes": True}
