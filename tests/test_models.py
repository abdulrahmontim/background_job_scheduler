from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.database import Base
from app.models.dlq import DeadLetterJob
from app.models.job import Job, JobStatus


def test_job_table_metadata():
    mapper = inspect(Job)
    assert mapper.persist_selectable.name == "jobs"

    columns = {column.name: column for column in mapper.columns}
    assert set(columns) == {
        "id",
        "type",
        "status",
        "payload",
        "scheduled_at",
        "created_at",
        "retry_count",
        "interval",
        "priority",
        "effective_priority",
        "dependencies",
        "error_message",
    }

    assert columns["id"].primary_key is True
    assert isinstance(columns["id"].type, PG_UUID)
    assert columns["type"].nullable is False
    assert columns["status"].nullable is False
    assert columns["status"].type.enum_class is JobStatus
    assert columns["payload"].nullable is False
    assert columns["scheduled_at"].nullable is False
    assert columns["created_at"].nullable is False
    assert columns["retry_count"].nullable is False
    assert columns["interval"].nullable is True
    assert columns["priority"].nullable is False
    assert columns["effective_priority"].nullable is False
    assert columns["dependencies"].nullable is False
    assert callable(columns["dependencies"].default.arg)
    assert columns["error_message"].nullable is True


def test_dead_letter_job_table_metadata():
    mapper = inspect(DeadLetterJob)
    assert mapper.persist_selectable.name == "dead_letter_jobs"

    columns = {column.name: column for column in mapper.columns}
    assert set(columns) == {
        "id",
        "original_job_id",
        "type",
        "payload",
        "failed_at",
        "error_message",
    }

    assert columns["id"].primary_key is True
    assert isinstance(columns["id"].type, PG_UUID)
    assert columns["original_job_id"].nullable is False
    assert columns["type"].nullable is False
    assert columns["payload"].nullable is False
    assert columns["failed_at"].nullable is False
    assert columns["error_message"].nullable is True


def test_models_registered_in_metadata():
    assert "jobs" in Base.metadata.tables
    assert "dead_letter_jobs" in Base.metadata.tables


def test_job_status_enum_values():
    assert [status.value for status in JobStatus] == [
        "pending",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ]
    assert JobStatus.PENDING.name == "PENDING"
    assert JobStatus.FAILED.value == "failed"
