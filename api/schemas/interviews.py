"""Pydantic schemas for Interview endpoints."""

from datetime import datetime
from typing import Optional, Any

from pydantic import field_validator

from .base import CamelModel


def _coerce_bool(v: Any) -> bool:
    """Convert None to False for boolean fields."""
    if v is None:
        return False
    return bool(v)


class InterviewCreate(CamelModel):
    """Schema for creating an interview."""

    application_id: int
    persona_id: Optional[int] = None


class InterviewListItem(CamelModel):
    """Schema for interview in list response."""

    id: int
    application_id: int
    candidate_name: str
    requisition_name: str
    interview_type: str
    status: str
    human_requested: bool = False
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message_count: int = 0

    @field_validator("human_requested", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool:
        return _coerce_bool(v)


class InterviewResponse(CamelModel):
    """Schema for full interview response."""

    id: int
    application_id: int
    candidate_name: str
    requisition_name: str
    interview_type: str
    status: str
    token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    human_requested: bool = False
    human_requested_at: Optional[datetime] = None
    persona_id: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message_count: int = 0

    @field_validator("human_requested", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool:
        return _coerce_bool(v)


class MessageResponse(CamelModel):
    """Schema for interview message."""

    id: int
    role: str
    content: Optional[str] = None
    created_at: datetime


class EvaluationResponse(CamelModel):
    """Schema for interview evaluation.

    Matches v1 evaluation schema with character gate, retention risk, etc.
    Uses 1-5 scale for individual scores, 0-100 for overall.
    """

    id: int
    interview_id: int

    # Granular scores (1-5 scale per v1)
    reliability_score: Optional[int] = None
    accountability_score: Optional[int] = None
    professionalism_score: Optional[int] = None
    communication_score: Optional[int] = None
    technical_score: Optional[int] = None
    growth_potential_score: Optional[int] = None
    overall_score: Optional[int] = None  # 0-100 scale

    # Summary and lists
    summary: Optional[str] = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    red_flags: list[str] = []

    # v1 evaluation fields
    character_passed: Optional[bool] = None  # Character gate pass/fail
    retention_risk: Optional[str] = None  # LOW, MEDIUM, HIGH
    authenticity_assessment: Optional[str] = None  # PASS, FAIL, REVIEW
    readiness: Optional[str] = None  # READY, NEEDS SUPPORT, NEEDS DEVELOPMENT

    # Recommendation and next steps
    recommendation: Optional[str] = None  # interview (4-5), review (3), decline (0-2)
    next_interview_focus: list[str] = []  # Focus areas for human interview

    model_version: Optional[str] = None
    created_at: datetime


# Public interview schemas (no auth required)
class PublicInterviewInfo(CamelModel):
    """Info returned for public interview access."""

    candidate_name: str
    position_title: str
    company_name: str = "CCFS"
    status: str
    expires_at: Optional[datetime] = None


class PublicMessageRequest(CamelModel):
    """Request to send a message in public interview."""

    content: str


class PublicMessageResponse(CamelModel):
    """Response for public interview message."""

    user_message: MessageResponse
    assistant_message: MessageResponse
    is_complete: bool = False
