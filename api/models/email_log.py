"""EmailLog model for email send tracking."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy import func

from api.config.database import Base


class EmailLog(Base):
    """
    Log of sent emails for tracking and debugging.
    """

    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Recipient
    to_email = Column(String(255), nullable=False)

    # Content
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    subject = Column(String(500), nullable=True)

    # Context
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)

    # Status: sent, failed, bounced
    status = Column(String(50), default="sent")
    error = Column(Text, nullable=True)

    # Tracking
    sent_at = Column(DateTime, default=func.getutcdate())
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<EmailLog(id={self.id}, to={self.to_email}, status={self.status})>"
