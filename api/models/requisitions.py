"""Requisition model for job openings."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Requisition(Base):
    """
    Job openings synced from Workday.
    """

    __tablename__ = "requisitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), nullable=False, unique=True)  # Workday Job_Requisition_ID

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)  # Brief for display
    detailed_description = Column(Text, nullable=True)  # Full JD for AI
    location = Column(String(255), nullable=True)

    # Assignment
    recruiter_id = Column(Integer, ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True)

    # Processing config
    is_active = Column(Boolean, default=True)
    sync_enabled = Column(Boolean, default=True)  # Whether to sync this requisition
    sync_interval_minutes = Column(Integer, default=15)  # Minutes between sync checks
    lookback_hours = Column(Integer, nullable=True)  # Override system default

    # Interview config
    interview_instructions = Column(Text, nullable=True)  # Extra prompts for AI
    auto_send_interview = Column(Boolean, default=False)
    auto_send_on_status = Column(String(100), nullable=True)  # Only send when candidate reaches this status

    # Workday sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    workday_data = Column(Text, nullable=True)  # Raw Workday fields (JSON string)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    # Relationships
    recruiter = relationship("Recruiter", back_populates="requisitions")
    applications = relationship("Application", back_populates="requisition")
    prompts = relationship("Prompt", back_populates="requisition")

    def __repr__(self) -> str:
        return f"<Requisition(id={self.id}, external_id={self.external_id}, name={self.name})>"
