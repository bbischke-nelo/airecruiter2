"""Pydantic schemas for Application endpoints."""

from datetime import datetime
from typing import Optional, Any

from .base import CamelModel


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
    risk_score: Optional[int] = None
    human_requested: bool = False
    compliance_review: bool = False
    created_at: datetime


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
    human_requested: bool
    compliance_review: bool
    artifacts: dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


class AnalysisResponse(CamelModel):
    """Schema for analysis response."""

    id: int
    application_id: int
    risk_score: Optional[int] = None
    relevance_summary: Optional[str] = None
    pros: list[str] = []
    cons: list[str] = []
    red_flags: list[str] = []
    suggested_questions: list[str] = []
    compliance_flags: list[str] = []
    model_version: Optional[str] = None
    created_at: datetime


class ReprocessRequest(CamelModel):
    """Request to reprocess an application."""

    from_step: str = "analyze"  # analyze, send_interview, evaluate, generate_report


class ReprocessResponse(CamelModel):
    """Response for reprocess request."""

    status: str
    queue_item_id: Optional[int] = None
    message: Optional[str] = None
