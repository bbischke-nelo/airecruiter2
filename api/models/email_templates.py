"""EmailTemplate model for email templates."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy import func

from api.config.database import Base


class EmailTemplate(Base):
    """
    Email templates for interview invites and alerts.
    """

    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(100), nullable=False)
    template_type = Column(String(50), nullable=False)  # interview_invite, alert

    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    def __repr__(self) -> str:
        return f"<EmailTemplate(id={self.id}, name={self.name}, type={self.template_type})>"
