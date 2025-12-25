"""Analysis model for AI resume analysis results."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Analysis(Base):
    """
    AI resume analysis results.

    Stores structured output from Claude resume analysis.
    """

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Scores (0-100 scale, consistent with evaluations)
    risk_score = Column(Integer, nullable=True)

    # Structured output
    relevance_summary = Column(Text, nullable=True)  # Job fit assessment
    pros = Column(Text, default="[]")  # JSON: ["Strong Python", ...]
    cons = Column(Text, default="[]")  # JSON: ["No management exp", ...]
    red_flags = Column(Text, default="[]")  # JSON: ["Employment gap", ...]

    # AI-generated content
    suggested_questions = Column(Text, default="[]")  # JSON: Interview questions
    compliance_flags = Column(Text, default="[]")  # JSON: Legal/ethical concerns

    # Raw AI response
    raw_response = Column(Text, nullable=True)  # JSON: Full AI output for debugging

    # Prompt used
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)

    # Metadata
    model_version = Column(String(50), nullable=True)  # claude-3-opus, etc.
    created_at = Column(DateTime, default=func.getutcdate())

    # Constraints
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_analyses_risk_score"),
    )

    # Relationships
    application = relationship("Application", back_populates="analysis")
    prompt = relationship("Prompt")

    def __repr__(self) -> str:
        return f"<Analysis(id={self.id}, application_id={self.application_id}, risk_score={self.risk_score})>"
