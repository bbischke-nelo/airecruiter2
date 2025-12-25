"""Pydantic schemas for Settings endpoints."""

from typing import Optional, Any

from .base import CamelModel


class SettingsResponse(CamelModel):
    """Schema for all settings response."""

    lookback_hours_default: int = 24
    lookback_hours_min: int = 1
    lookback_hours_max: int = 168
    interview_token_expiry_days: int = 7
    email_from_address: str = "noreply@company.com"
    email_from_name: str = "AIRecruiter"
    default_recruiter_id: Optional[int] = None


class SettingsUpdate(CamelModel):
    """Schema for updating settings (all fields optional)."""

    lookback_hours_default: Optional[int] = None
    lookback_hours_min: Optional[int] = None
    lookback_hours_max: Optional[int] = None
    interview_token_expiry_days: Optional[int] = None
    email_from_address: Optional[str] = None
    email_from_name: Optional[str] = None
    default_recruiter_id: Optional[int] = None
