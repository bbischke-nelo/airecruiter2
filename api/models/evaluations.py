"""Evaluation model for AI-generated interview evaluation scores."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Evaluation(Base):
    """
    AI interview factual summary.

    Stores structured factual output from Claude interview analysis.
    NO scoring - humans make all decisions.
    """

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Factual summary (replaces scoring)
    summary = Column(Text, nullable=True)  # Factual interview summary
    interview_highlights = Column(Text, nullable=True)  # JSON: Key points from interview
    next_interview_focus = Column(Text, default="[]")  # JSON: Areas to explore in live interview

    # Full interview transcript
    transcript = Column(Text, nullable=True)

    # Raw AI response
    raw_response = Column(Text, nullable=True)  # JSON

    # Prompt used
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)

    # Metadata
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.getutcdate())

    # Relationships
    interview = relationship("Interview", back_populates="evaluation")
    prompt = relationship("Prompt")

    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, interview_id={self.interview_id})>"
