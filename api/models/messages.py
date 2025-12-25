"""Message model for interview conversation log."""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Numeric
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Message(Base):
    """
    Conversation log for interviews.

    Stores each message in the interview conversation.
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Message
    role = Column(String(20), nullable=False)  # system, assistant, user
    content = Column(Text, nullable=True)

    # Optional per-message analysis
    sentiment = Column(Numeric(3, 2), nullable=True)  # -1.00 to 1.00
    topics = Column(Text, nullable=True)  # JSON: ["salary", "remote"]

    # Timestamp
    created_at = Column(DateTime, default=func.getutcdate())

    # Relationships
    interview = relationship("Interview", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role})>"
