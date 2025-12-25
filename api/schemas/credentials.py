"""Pydantic schemas for Credentials endpoints."""

from datetime import datetime
from typing import Optional

from .base import CamelModel


class CredentialCreate(CamelModel):
    """Schema for saving credentials."""

    tenant_url: str
    tenant_id: str
    client_id: str
    client_secret: str
    refresh_token: Optional[str] = None


class CredentialStatusResponse(CamelModel):
    """Schema for credential status response (no secrets)."""

    has_credentials: bool
    is_valid: bool
    tenant_id: Optional[str] = None
    tenant_url: Optional[str] = None
    last_validated: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class CredentialTestResponse(CamelModel):
    """Response for credential test."""

    success: bool
    message: str
    tenant_id: Optional[str] = None
