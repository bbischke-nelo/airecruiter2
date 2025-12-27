"""Pydantic schemas for Application endpoints."""

from datetime import datetime
from typing import Optional, Any, List

from pydantic import field_validator

from .base import CamelModel


def _coerce_bool(v: Any) -> bool:
    """Convert None to False for boolean fields."""
    if v is None:
        return False
    return bool(v)


# Rejection reason codes are now fetched dynamically from Workday
# via the GET /settings/dispositions endpoint.
# No free-form comments allowed - they become discovery liabilities in litigation


class ApplicationListItem(CamelModel):
    """Schema for application in list response."""

    id: int
    requisition_id: int
    requisition_name: str
    external_application_id: str
    candidate_name: str
    candidate_email: Optional[str] = None
    status: str
    workday_status: Optional[str] = None
    has_analysis: bool = False
    has_interview: bool = False
    has_report: bool = False
    # Extracted facts summary for grid triage
    jd_match_percentage: Optional[int] = None
    avg_tenure_months: Optional[float] = None
    current_title: Optional[str] = None
    current_employer: Optional[str] = None
    total_experience_months: Optional[int] = None
    months_since_last_employment: Optional[int] = None
    compliance_review: bool = False
    # Decision tracking
    rejection_reason_code: Optional[str] = None
    created_at: datetime

    # Validators to coerce None to False
    @field_validator("compliance_review", "has_analysis", "has_interview", "has_report", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool:
        return _coerce_bool(v)


class ApplicationResponse(CamelModel):
    """Schema for full application response."""

    id: int
    requisition_id: int
    external_application_id: str
    external_candidate_id: Optional[str] = None
    candidate_name: str
    candidate_email: Optional[str] = None
    status: str
    workday_status: Optional[str] = None
    workday_status_changed: Optional[datetime] = None
    compliance_review: bool = False
    artifacts: dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    # Validators to coerce None to False
    @field_validator("compliance_review", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> bool:
        return _coerce_bool(v)


class ReprocessRequest(CamelModel):
    """Request to reprocess an application."""

    from_step: str = "analyze"  # analyze, send_interview, evaluate, generate_report


class ReprocessResponse(CamelModel):
    """Response for reprocess request."""

    status: str
    queue_item_id: Optional[int] = None
    message: Optional[str] = None


# Human-in-the-Loop Decision Schemas

class AdvanceRequest(CamelModel):
    """Request to advance an application."""

    notes: Optional[str] = None
    skip_interview: bool = False  # If true, advance directly to live_interview_pending


class RejectRequest(CamelModel):
    """Request to reject an application.

    Note: No comment field - free-form comments are discovery liabilities.
    The reason codes come from Workday dispositions and are designed to be
    legally defensible on their own.
    """

    reason_code: str  # Disposition ID from Workday (e.g., "Not Interested in Position")


class HoldRequest(CamelModel):
    """Request to put an application on hold.

    Note: No free-form reason field - same discovery liability as reject comments.
    """

    pass


class UnholdRequest(CamelModel):
    """Request to remove an application from hold."""

    pass


class UnrejectRequest(CamelModel):
    """Request to unreject an application (move back to review).

    Note: This is an unusual action that requires justification.
    The comment is stored for audit purposes but should be brief
    and factual (e.g., "Rejected in error - meant different candidate").
    WARNING: This will NOT sync to Workday - the candidate will remain
    rejected in Workday.
    """

    comment: str  # Required - explain why unreject is needed


class DecisionResponse(CamelModel):
    """Response for decision actions (advance/reject/hold)."""

    success: bool
    application_id: int
    action: str  # advance, reject, hold, unhold
    from_status: str
    to_status: str
    message: str


class ApplicationDecisionItem(CamelModel):
    """Schema for decision audit trail item."""

    id: int
    application_id: int
    action: str
    from_status: str
    to_status: str
    reason_code: Optional[str] = None
    comment: Optional[str] = None
    user_id: int
    created_at: datetime


class ExtractedFactsResponse(CamelModel):
    """Schema for extracted facts from analysis."""

    id: int
    application_id: int
    extraction_version: Optional[str] = None
    extraction_notes: Optional[str] = None
    extracted_facts: Optional[dict] = None
    relevance_summary: Optional[str] = None
    pros: List[dict] = []
    cons: List[dict] = []
    suggested_questions: List[dict] = []
    model_version: Optional[str] = None
    created_at: datetime


class AnalysisResponse(CamelModel):
    """Schema for analysis response (updated for fact extraction)."""

    id: int
    application_id: int
    # Extracted facts (replaces risk_score)
    extraction_version: Optional[str] = None
    extraction_notes: Optional[str] = None
    extracted_facts: Optional[dict] = None
    relevance_summary: Optional[str] = None
    pros: List[Any] = []
    cons: List[Any] = []
    suggested_questions: List[Any] = []
    compliance_flags: List[str] = []
    model_version: Optional[str] = None
    created_at: datetime
