"""Setting model for system configuration key-value store."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy import func
from sqlalchemy.sql.elements import quoted_name

from api.config.database import Base


class Setting(Base):
    """
    System configuration key-value store.

    Stores application settings that can be modified at runtime.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Use quoted_name to properly escape 'key' which is a SQL Server reserved word
    key = Column(quoted_name('key', quote=True), String(100), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    # Indexes - use quoted_name for index too
    __table_args__ = (
        Index("idx_settings_key", quoted_name('key', quote=True)),
    )

    def __repr__(self) -> str:
        return f"<Setting(key={self.key})>"


# Default settings to seed
DEFAULT_SETTINGS = {
    # Email settings
    "email_from_address": ("jobs@ccfs.com", "Email sender address"),
    "email_from_name": ("CCFS Talent Team", "Email sender name"),

    # Storage settings
    "s3_bucket": ("airecruiter-artifacts", "S3 bucket for artifacts"),

    # Interview settings
    "interview_token_expiry_days": ("7", "Days until interview token expires"),

    # Global requisition defaults (NULL on requisition = use these)
    "auto_send_interview_default": ("false", "Default: auto-send AI interviews (true/false)"),
    "advance_stage_id": ("", "Workday stage ID to move candidates to when advanced"),
    "reject_disposition_id": ("", "Workday disposition ID to use when rejecting candidates"),

    # Legacy (kept for backwards compatibility)
    "default_recruiter_id": ("", "Default recruiter ID for new requisitions"),
}
