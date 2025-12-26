"""Rejection reasons model for recruiter dropdown."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy import func

from api.config.database import Base


class RejectionReason(Base):
    """
    Rejection reasons for recruiter dropdown.

    When a recruiter rejects a candidate, they select from this list.
    The external_id is sent to the TMS for disposition.
    """

    __tablename__ = "rejection_reasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)  # Internal code
    external_id = Column(String(100), nullable=False)  # TMS disposition ID
    name = Column(String(255), nullable=False)  # Display name
    requires_comment = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    def __repr__(self) -> str:
        return f"<RejectionReason(code={self.code}, name={self.name})>"


# Default rejection reasons
DEFAULT_REJECTION_REASONS = [
    {"code": "EXPERIENCE_SKILLS", "external_id": "Experience/Skills", "name": "Experience/Skills"},
    {"code": "NOT_INTERESTED", "external_id": "Not Interested in Position", "name": "Not Interested in Position"},
    {"code": "OFF_THE_MARKET", "external_id": "Off the Market", "name": "Off the Market"},
    {"code": "DIDNT_MEET_GUIDELINES", "external_id": "Didn't Meet Hiring Guidelines", "name": "Didn't Meet Hiring Guidelines"},
    {"code": "CANDIDATE_WITHDRAWN", "external_id": "Candidate Withdrawn", "name": "Candidate Withdrawn"},
    {"code": "REQUISITION_CLOSED", "external_id": "Job Requisition Closed or Cancelled", "name": "Requisition Closed"},
    {"code": "ANOTHER_CANDIDATE_HIRED", "external_id": "Another Candidate Hired", "name": "Another Candidate Hired"},
    {"code": "NO_SHOW", "external_id": "No Show or Failed Road Test", "name": "No Show"},
]
