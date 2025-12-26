"""ApplicationDecision model for audit trail of human recruiter decisions."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


# Valid rejection reason codes (legally defensible)
VALID_REASON_CODES = {
    "QUAL_LICENSE",       # Missing required license/certification
    "QUAL_EXPERIENCE",    # Does not meet minimum experience requirement
    "QUAL_SKILLS",        # Missing required technical skills
    "QUAL_EDUCATION",     # Does not meet education requirement
    "RETENTION_RISK",     # Objective retention concern (avg tenure < threshold)
    "RECENCY_OF_SKILLS",  # Skills are outdated
    "OVERQUALIFIED",      # Overqualified (requires comment)
    "LOCATION_MISMATCH",  # Unable to work at job location
    "SCHEDULE_MISMATCH",  # Unable to work required schedule
    "SALARY_MISMATCH",    # Compensation expectations misaligned
    "WITHDREW",           # Candidate withdrew application
    "NO_RESPONSE",        # No response to interview invitation
    "INTERVIEW_INCOMPLETE",  # Did not complete AI interview
    "INTERVIEW_PERFORMANCE", # Did not meet standards in interview
    "WORK_AUTHORIZATION",    # Cannot provide required work authorization
    "DID_NOT_SHOW",       # Candidate did not attend scheduled interview
    "POSITION_FILLED",    # Position filled by another candidate
    "DUPLICATE",          # Duplicate application
    "OTHER",              # Other reason (requires comment)
}

# Reason codes that require a comment
REASON_CODES_REQUIRING_COMMENT = {"OTHER", "OVERQUALIFIED"}


class ApplicationDecision(Base):
    """
    Audit trail for human recruiter decisions.

    Logs every advance, reject, hold, or unhold action with full context
    for legal defensibility.
    """

    __tablename__ = "application_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Decision details
    action = Column(String(20), nullable=False)  # advance, reject, hold, unhold
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)
    reason_code = Column(String(50), nullable=True)  # Required for reject
    comment = Column(Text, nullable=True)

    # Who made the decision
    user_id = Column(Integer, nullable=False)

    # Metadata
    created_at = Column(DateTime, server_default=func.getutcdate(), nullable=False)

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_application_decisions_application", "application_id"),
        Index("ix_application_decisions_user", "user_id"),
        Index("ix_application_decisions_reason", "reason_code"),
        Index("ix_application_decisions_created", "created_at"),
    )

    # Relationships
    application = relationship("Application", back_populates="decisions")

    def __repr__(self) -> str:
        return f"<ApplicationDecision(id={self.id}, action={self.action}, reason={self.reason_code})>"
