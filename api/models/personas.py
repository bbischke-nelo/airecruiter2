"""Persona model for AI interviewer personalities."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy import func

from api.config.database import Base


class Persona(Base):
    """
    AI interviewer personalities.

    Defines system prompts for different interview styles.
    """

    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # The AI personality/system prompt
    system_prompt_template = Column(Text, nullable=False)

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    def __repr__(self) -> str:
        return f"<Persona(id={self.id}, name={self.name})>"
