"""Pydantic schemas for Requisition endpoints."""

from datetime import datetime
from typing import Optional, Any

from .base import CamelModel


class RequisitionBase(CamelModel):
    """Base requisition fields."""

    name: str
    description: Optional[str] = None
    location: Optional[str] = None


class RequisitionCreate(RequisitionBase):
    """Schema for creating a requisition."""

    external_id: str
    detailed_description: Optional[str] = None
    recruiter_id: Optional[int] = None
    is_active: bool = True
    sync_interval_minutes: int = 15
    interview_instructions: Optional[str] = None
    # 3-state: None = use global default, True = always send, False = never send
    auto_send_interview: Optional[bool] = None
    auto_send_on_status: Optional[str] = None


class RequisitionUpdate(CamelModel):
    """Schema for updating a requisition (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    detailed_description: Optional[str] = None
    location: Optional[str] = None
    recruiter_id: Optional[int] = None
    is_active: Optional[bool] = None
    sync_interval_minutes: Optional[int] = None
    interview_instructions: Optional[str] = None
    auto_send_interview: Optional[bool] = None
    auto_send_on_status: Optional[str] = None


class RequisitionResponse(CamelModel):
    """Schema for full requisition response."""

    id: int
    external_id: str
    name: str
    description: Optional[str] = None
    detailed_description: Optional[str] = None
    location: Optional[str] = None
    recruiter_id: Optional[int] = None
    is_active: bool
    sync_interval_minutes: int
    interview_instructions: Optional[str] = None
    # 3-state: None = use global default, True = always send, False = never send
    auto_send_interview: Optional[bool] = None
    auto_send_on_status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    external_data: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RequisitionListItem(CamelModel):
    """Schema for requisition in list response."""

    id: int
    external_id: str
    name: str
    location: Optional[str] = None
    recruiter_id: Optional[int] = None
    recruiter_name: Optional[str] = None
    is_active: bool
    # 3-state: None = use global default, True = always send, False = never send
    auto_send_interview: Optional[bool] = None
    application_count: int = 0
    pending_count: int = 0
    last_synced_at: Optional[datetime] = None
    created_at: datetime


class SyncResponse(CamelModel):
    """Response for sync trigger."""

    status: str
    queue_item_id: Optional[int] = None
    message: Optional[str] = None
