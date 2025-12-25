"""Prompt model for AI prompt templates."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import func, Index
from sqlalchemy.orm import relationship

from api.config.database import Base


class Prompt(Base):
    """
    AI prompt templates.

    Stores templates for resume analysis, interviews, and evaluations.
    Can be global or requisition-specific.
    """

    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity
    name = Column(String(255), nullable=False)
    # resume_analysis, interview, self_service_interview, evaluation, interview_email
    prompt_type = Column(String(50), nullable=False)

    # Content
    template_content = Column(Text, nullable=False)
    schema_content = Column(Text, nullable=True)  # JSON schema for structured output

    # Scope: NULL = global, otherwise requisition-specific override
    requisition_id = Column(
        Integer,
        ForeignKey("requisitions.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # One default per type

    # Versioning
    version = Column(Integer, default=1)
    description = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_prompts_type", "prompt_type"),
        Index("idx_prompts_requisition", "requisition_id"),
    )

    # Relationships
    requisition = relationship("Requisition", back_populates="prompts")

    def __repr__(self) -> str:
        return f"<Prompt(id={self.id}, name={self.name}, type={self.prompt_type})>"
