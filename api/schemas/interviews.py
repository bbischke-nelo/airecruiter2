"""Pydantic schemas for Interview endpoints."""

from datetime import datetime
from typing import Optional, Literal

from .base import CamelModel


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
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message_count: int = 0


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
    persona_id: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message_count: int = 0


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


# Prepare/Activate interview schemas (2-step send flow)
class EmailPreview(CamelModel):
    """Email preview for interview invitation."""

    to_email: str
    subject: str
    body_html: str


class PrepareInterviewRequest(CamelModel):
    """Request to prepare an interview (creates draft, returns preview)."""

    mode: Literal["email", "link_only"] = "email"  # Whether email will be sent
    email_override: Optional[str] = None  # Override candidate email
    persona_id: Optional[int] = None
    expiry_days: int = 7


class PrepareInterviewResponse(CamelModel):
    """Response for prepare interview request."""

    interview_id: int
    interview_token: str
    interview_url: str
    expires_at: datetime
    email_preview: Optional[EmailPreview] = None  # Only for email mode


class ActivateInterviewRequest(CamelModel):
    """Request to activate an interview (send email or just make link active)."""

    method: Literal["email", "link_only"]  # "email" sends email, "link_only" just activates
    email_override: Optional[str] = None  # Can override at send time too
    custom_subject: Optional[str] = None  # Custom email subject (if edited)
    custom_html: Optional[str] = None  # Custom email HTML body (if edited)


class ActivateInterviewResponse(CamelModel):
    """Response for activate interview request."""

    interview_id: int
    interview_url: str
    expires_at: datetime
    email_sent: bool
    email_sent_to: Optional[str] = None


# Proxy interview schemas (recruiter conducting on candidate's behalf)
class StartProxyInterviewRequest(CamelModel):
    """Request to start a proxy interview."""

    persona_id: Optional[int] = None


class StartProxyInterviewResponse(CamelModel):
    """Response for starting a proxy interview."""

    interview_id: int
    status: str
    initial_message: MessageResponse


class ProxyMessageRequest(CamelModel):
    """Request to send a message in proxy interview."""

    content: str  # Candidate's response (typed by recruiter)


class ProxyMessageResponse(CamelModel):
    """Response for proxy interview message."""

    user_message: MessageResponse
    ai_response: MessageResponse
    is_complete: bool = False


class EndProxyResponse(CamelModel):
    """Response for ending a proxy interview."""

    interview_id: int
    status: str
    message_count: int
    completed_at: datetime
