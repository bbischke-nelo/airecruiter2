"""Pydantic schemas for Settings endpoints."""

from typing import Optional, Any

from .base import CamelModel


class SettingsResponse(CamelModel):
    """Schema for all settings response."""

    # Email settings
    email_from_address: str = "noreply@company.com"
    email_from_name: str = "AIRecruiter"

    # Interview settings
    interview_token_expiry_days: int = 7

    # Global requisition defaults (used when requisition field is NULL)
    auto_send_interview_default: bool = False
    advance_stage_id: Optional[str] = None
    reject_disposition_id: Optional[str] = None

    # Legacy
    default_recruiter_id: Optional[int] = None


class SettingsUpdate(CamelModel):
    """Schema for updating settings (all fields optional)."""

    # Email settings
    email_from_address: Optional[str] = None
    email_from_name: Optional[str] = None

    # Interview settings
    interview_token_expiry_days: Optional[int] = None

    # Global requisition defaults
    auto_send_interview_default: Optional[bool] = None
    advance_stage_id: Optional[str] = None
    reject_disposition_id: Optional[str] = None

    # Legacy
    default_recruiter_id: Optional[int] = None
