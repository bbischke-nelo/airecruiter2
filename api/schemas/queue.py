"""Pydantic schemas for Queue endpoints."""

from datetime import datetime
from typing import Optional

from .base import CamelModel


class QueueItem(CamelModel):
    """Schema for queue item."""

    id: int
    job_type: str
    application_id: int
    requisition_name: Optional[str] = None
    candidate_name: Optional[str] = None
    status: str
    priority: int
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scheduled_for: datetime


class QueueStatusResponse(CamelModel):
    """Schema for queue status response."""

    pending: int
    running: int
    completed: int
    failed: int
    dead: int
    items: list[QueueItem] = []


class QueueAddRequest(CamelModel):
    """Request to add item to queue."""

    job_type: str
    application_id: Optional[int] = None
    requisition_id: Optional[int] = None
    priority: int = 0


class QueueAddResponse(CamelModel):
    """Response for adding item to queue."""

    id: int
    job_type: str
    status: str
