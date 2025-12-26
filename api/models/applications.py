"""Application model for candidate applications."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import func, UniqueConstraint
from sqlalchemy.orm import relationship

from api.config.database import Base


class Application(Base):
    """
    Candidate applications being processed.

    This is the central entity in the processing pipeline.
    """

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"), nullable=False)

    # Workday IDs
    external_application_id = Column(String(255), nullable=False)  # Job_Application_ID
    external_candidate_id = Column(String(255), nullable=True)  # Candidate_ID

    # Candidate info (denormalized for convenience)
    candidate_name = Column(String(255), nullable=False)
    candidate_email = Column(String(255), nullable=True)

    # Processing status
    # new, analyzing, analyzed, interview_pending, interview_in_progress,
    # interview_complete, report_pending, complete, failed, skipped
    status = Column(String(50), nullable=False, default="new")

    # Workday status tracking
    workday_status = Column(String(100), nullable=True)  # Current status in Workday
    workday_status_changed = Column(DateTime, nullable=True)

    # Flags
    human_requested = Column(Boolean, default=False)  # Candidate asked for human
    compliance_review = Column(Boolean, default=False)  # Flagged for review

    # Artifacts (S3 keys) - stored as JSON string
    # {"resume": "s3://...", "analysis": "s3://...", "report": "s3://..."}
    artifacts = Column(Text, default="{}")

    # Decision tracking (Human-in-the-Loop)
    rejection_reason_code = Column(String(50), nullable=True)
    rejection_comment = Column(Text, nullable=True)
    rejected_by = Column(Integer, ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    advanced_by = Column(Integer, ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True)
    advanced_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())
    processed_at = Column(DateTime, nullable=True)  # When fully processed

    # Constraints
    __table_args__ = (
        UniqueConstraint("requisition_id", "external_application_id", name="uq_applications_req_ext"),
    )

    # Relationships
    requisition = relationship("Requisition", back_populates="applications")
    analysis = relationship("Analysis", back_populates="application", uselist=False)
    interviews = relationship("Interview", back_populates="application")
    reports = relationship("Report", back_populates="application")
    activities = relationship("Activity", back_populates="application")
    jobs = relationship("Job", back_populates="application")
    decisions = relationship("ApplicationDecision", back_populates="application", order_by="ApplicationDecision.created_at.desc()")

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, candidate={self.candidate_name}, status={self.status})>"
