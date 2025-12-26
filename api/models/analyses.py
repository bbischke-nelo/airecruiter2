"""Analysis model for AI resume analysis results."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Analysis(Base):
    """
    AI resume fact extraction results.

    Stores structured factual output from Claude resume analysis.
    NO scoring - humans make all decisions.
    """

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Extracted facts (JSON blob with employment, skills, certs, education, timeline)
    extracted_facts = Column(Text, nullable=True)
    extraction_version = Column(String(20), nullable=True)  # Schema version
    extraction_notes = Column(Text, nullable=True)  # Flags for manual review

    # Structured output (kept for observations tied to JD)
    relevance_summary = Column(Text, nullable=True)  # Factual summary
    pros = Column(Text, default="[]")  # JSON: Factual observations tied to JD
    cons = Column(Text, default="[]")  # JSON: Factual gaps relative to JD

    # AI-generated content
    suggested_questions = Column(Text, default="[]")  # JSON: Clarifying questions about facts
    compliance_flags = Column(Text, default="[]")  # JSON: Legal/ethical concerns

    # Raw AI response
    raw_response = Column(Text, nullable=True)  # JSON: Full AI output for debugging

    # Prompt used
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)

    # Metadata
    model_version = Column(String(50), nullable=True)  # claude-3-opus, etc.
    created_at = Column(DateTime, default=func.getutcdate())

    # Relationships
    application = relationship("Application", back_populates="analysis")
    prompt = relationship("Prompt")

    def __repr__(self) -> str:
        return f"<Analysis(id={self.id}, application_id={self.application_id})>"
