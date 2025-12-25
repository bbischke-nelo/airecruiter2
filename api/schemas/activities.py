"""Pydantic schemas for Activity/Logs endpoints."""

from datetime import datetime
from typing import Optional, Any

from .base import CamelModel


class ActivityResponse(CamelModel):
    """Schema for activity log entry."""

    id: int
    action: str
    application_id: Optional[int] = None
    requisition_id: Optional[int] = None
    recruiter_id: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime


class ActivityListItem(CamelModel):
    """Schema for activity in list response."""

    id: int
    action: str
    application_id: Optional[int] = None
    candidate_name: Optional[str] = None
    requisition_name: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime
