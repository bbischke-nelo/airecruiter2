"""Pydantic schemas for Prompt endpoints."""

from datetime import datetime
from typing import Optional

from .base import CamelModel


class PromptBase(CamelModel):
    """Base prompt fields."""

    name: str
    prompt_type: str  # resume_analysis, interview, evaluation, interview_email
    template_content: str
    schema_content: Optional[str] = None
    description: Optional[str] = None


class PromptCreate(PromptBase):
    """Schema for creating a prompt."""

    requisition_id: Optional[int] = None
    is_default: bool = False


class PromptUpdate(CamelModel):
    """Schema for updating a prompt (all fields optional)."""

    name: Optional[str] = None
    template_content: Optional[str] = None
    schema_content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class PromptResponse(PromptBase):
    """Schema for prompt response."""

    id: int
    requisition_id: Optional[int] = None
    is_active: bool
    is_default: bool
    version: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class PromptListItem(CamelModel):
    """Schema for prompt in list response."""

    id: int
    name: str
    prompt_type: str
    requisition_id: Optional[int] = None
    is_active: bool
    is_default: bool
    version: int
    created_at: datetime
