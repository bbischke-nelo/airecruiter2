"""Report model for generated PDF reports."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship

from api.config.database import Base


class Report(Base):
    """
    Generated PDF reports for candidates.

    Stores S3 location and Workday upload status.
    """

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)

    # Storage
    s3_key = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)

    # Upload status
    uploaded_to_workday = Column(Boolean, default=False)
    workday_document_id = Column(String(255), nullable=True)  # Workday attachment ID
    uploaded_at = Column(DateTime, nullable=True)

    # Content included
    includes_analysis = Column(Boolean, default=True)
    includes_interview = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())

    # Relationships
    application = relationship("Application", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, uploaded={self.uploaded_to_workday})>"
