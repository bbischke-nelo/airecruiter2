"""Activity model for business audit trail."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Activity(Base):
    """
    Business audit trail.

    Records significant business events (NOT for operational logs - those go to CloudWatch).
    """

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # What happened
    # status_changed, interview_sent, interview_completed, report_uploaded, etc.
    action = Column(String(100), nullable=False)

    # Context
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
    )
    requisition_id = Column(
        Integer,
        ForeignKey("requisitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    recruiter_id = Column(
        Integer,
        ForeignKey("recruiters.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Details (JSON)
    # {"from_status": "new", "to_status": "analyzed", "by": "system"}
    details = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=func.getutcdate())

    # Indexes
    __table_args__ = (
        Index("idx_activities_application", "application_id"),
        Index("idx_activities_created", "created_at"),
    )

    # Relationships
    application = relationship("Application", back_populates="activities")

    def __repr__(self) -> str:
        return f"<Activity(id={self.id}, action={self.action})>"
