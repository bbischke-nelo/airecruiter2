"""Evaluation model for AI-generated interview evaluation scores."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, CheckConstraint, Boolean
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Evaluation(Base):
    """
    AI-generated interview evaluation scores.

    Stores structured evaluation output from Claude.
    Uses v1 scoring scale (1-5) for individual scores, 0-100 for overall.
    """

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Granular scores (1-5 scale per v1)
    reliability_score = Column(Integer, nullable=True)
    accountability_score = Column(Integer, nullable=True)
    professionalism_score = Column(Integer, nullable=True)
    communication_score = Column(Integer, nullable=True)
    technical_score = Column(Integer, nullable=True)
    growth_potential_score = Column(Integer, nullable=True)

    # Computed overall (0-100 scale)
    overall_score = Column(Integer, nullable=True)

    # Textual analysis
    summary = Column(Text, nullable=True)
    strengths = Column(Text, default="[]")  # JSON
    weaknesses = Column(Text, default="[]")  # JSON
    red_flags = Column(Text, default="[]")  # JSON

    # v1 evaluation fields
    character_passed = Column(Boolean, nullable=True)  # Character gate pass/fail
    retention_risk = Column(String(20), nullable=True)  # LOW, MEDIUM, HIGH
    authenticity_assessment = Column(String(20), nullable=True)  # PASS, FAIL, REVIEW
    readiness = Column(String(50), nullable=True)  # READY, NEEDS SUPPORT, NEEDS DEVELOPMENT

    # Recommendation: interview (4-5), review (3), decline (0-2)
    recommendation = Column(String(50), nullable=True)
    next_interview_focus = Column(Text, default="[]")  # JSON: Focus areas for next round

    # Full interview transcript
    transcript = Column(Text, nullable=True)

    # Raw AI response
    raw_response = Column(Text, nullable=True)  # JSON

    # Prompt used
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)

    # Metadata
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.getutcdate())

    # Constraints
    __table_args__ = (
        CheckConstraint("reliability_score BETWEEN 0 AND 10", name="ck_eval_reliability"),
        CheckConstraint("accountability_score BETWEEN 0 AND 10", name="ck_eval_accountability"),
        CheckConstraint("professionalism_score BETWEEN 0 AND 10", name="ck_eval_professionalism"),
        CheckConstraint("communication_score BETWEEN 0 AND 10", name="ck_eval_communication"),
        CheckConstraint("technical_score BETWEEN 0 AND 10", name="ck_eval_technical"),
        CheckConstraint("growth_potential_score BETWEEN 0 AND 10", name="ck_eval_growth"),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="ck_eval_overall"),
    )

    # Relationships
    interview = relationship("Interview", back_populates="evaluation")
    prompt = relationship("Prompt")

    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, overall_score={self.overall_score}, recommendation={self.recommendation})>"
