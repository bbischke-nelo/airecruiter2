"""Job model for the processing queue."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Job(Base):
    """
    Queue for processing jobs.

    Worker polls this table to claim and execute jobs.
    """

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job info
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"), nullable=True)
    # sync, analyze, send_interview, evaluate, generate_report, upload_report
    job_type = Column(String(50), nullable=False)

    # Queue status: pending, running, completed, failed, dead
    status = Column(String(50), default="pending")

    priority = Column(Integer, default=0)  # Higher = more urgent
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Job payload (JSON)
    payload = Column(Text, nullable=True)

    # Error tracking
    last_error = Column(Text, nullable=True)

    # Timing
    created_at = Column(DateTime, default=func.getutcdate())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, default=func.getutcdate())  # For delayed/retry jobs

    # Indexes for efficient queue operations
    __table_args__ = (
        Index("idx_jobs_pending", "scheduled_for", "priority"),
        Index("idx_jobs_application", "application_id"),
        Index("idx_jobs_requisition", "requisition_id"),
    )

    # Relationships
    application = relationship("Application", back_populates="jobs")
    requisition = relationship("Requisition")

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"
