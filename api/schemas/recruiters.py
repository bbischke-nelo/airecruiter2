"""Pydantic schemas for Recruiter endpoints."""

from datetime import datetime
from typing import Optional

from .base import CamelModel


class RecruiterBase(CamelModel):
    """Base recruiter fields."""

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    public_contact_info: Optional[str] = None


class RecruiterCreate(RecruiterBase):
    """Schema for creating a recruiter."""

    external_id: Optional[str] = None


class RecruiterUpdate(CamelModel):
    """Schema for updating a recruiter (all fields optional)."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    public_contact_info: Optional[str] = None
    is_active: Optional[bool] = None


class RecruiterResponse(RecruiterBase):
    """Schema for recruiter response."""

    id: int
    external_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class RecruiterListItem(CamelModel):
    """Schema for recruiter in list response."""

    id: int
    name: str
    email: Optional[str] = None
    title: Optional[str] = None
    is_active: bool
    requisition_count: int = 0
