"""ReportTemplate model for PDF report templates."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy import func

from api.config.database import Base


class ReportTemplate(Base):
    """
    HTML templates for generating PDF reports.

    Types: analysis, interview_report
    """

    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(100), nullable=False)
    template_type = Column(String(50), nullable=False)  # analysis, interview_report

    # HTML content (Jinja2 template)
    body_html = Column(Text, nullable=False)

    # Optional CSS override
    custom_css = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    def __repr__(self) -> str:
        return f"<ReportTemplate(id={self.id}, name={self.name}, type={self.template_type})>"
