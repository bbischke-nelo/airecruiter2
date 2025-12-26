"""Interview model for AI interview sessions."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Interview(Base):
    """
    AI interview sessions.

    Interview Types:
    - self_service: Candidate conducts interview via token link
    - proxy: Recruiter conducts interview on candidate's behalf

    Status Values:
    - draft: Created but not activated (pending recruiter confirmation)
    - scheduled: Ready for candidate (token active)
    - in_progress: Interview started
    - completed: Interview finished
    - abandoned: Cancelled
    - expired: Token expired
    """

    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)

    # Type: self_service (candidate via link) or proxy (recruiter on behalf)
    interview_type = Column(String(20), default="self_service")

    # Self-service access
    token = Column(String(64), unique=True, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # Status: draft, scheduled, in_progress, completed, abandoned, expired
    status = Column(String(50), default="scheduled")

    # Configuration
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)

    # Recruiter who conducted proxy interview (NULL for self-service)
    recruiter_id = Column(Integer, ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True)

    # Email override for self-service interviews
    candidate_email = Column(String(255), nullable=True)

    # When the interview invite email was actually sent (NULL if link-only)
    invite_sent_at = Column(DateTime, nullable=True)

    # Flags
    human_requested = Column(Boolean, default=False)
    human_requested_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.getutcdate())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Extra context
    extra_data = Column(Text, nullable=True)  # JSON

    # Relationships
    application = relationship("Application", back_populates="interviews")
    persona = relationship("Persona")
    recruiter = relationship("Recruiter", back_populates="interviews")
    messages = relationship("Message", back_populates="interview", cascade="all, delete-orphan")
    evaluation = relationship("Evaluation", back_populates="interview", uselist=False)

    def __repr__(self) -> str:
        return f"<Interview(id={self.id}, status={self.status}, type={self.interview_type})>"
