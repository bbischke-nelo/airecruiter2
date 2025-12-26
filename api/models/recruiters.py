"""Recruiter model for recruiter profiles."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Recruiter(Base):
    """
    Recruiter profiles for assignment and email templates.
    """

    __tablename__ = "recruiters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), unique=True, nullable=True)  # Workday Worker ID

    # Identity
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    title = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)

    # For email templates
    public_contact_info = Column(Text, nullable=True)  # Free-form contact block

    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    # Relationships
    requisitions = relationship("Requisition", back_populates="recruiter")
    interviews = relationship("Interview", back_populates="recruiter")

    def __repr__(self) -> str:
        return f"<Recruiter(id={self.id}, name={self.name})>"
