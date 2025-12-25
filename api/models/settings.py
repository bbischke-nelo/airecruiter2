"""Setting model for system configuration key-value store."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy import func

from api.config.database import Base


class Setting(Base):
    """
    System configuration key-value store.

    Stores application settings that can be modified at runtime.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Using 'setting_key' instead of 'key' to avoid SQL Server reserved word issues
    setting_key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    # Indexes
    __table_args__ = (
        Index("idx_settings_key", "setting_key"),
    )

    def __repr__(self) -> str:
        return f"<Setting(key={self.setting_key})>"


# Default settings to seed
DEFAULT_SETTINGS = {
    "lookback_hours_min": ("1", "Minimum hours to look back for sync"),
    "lookback_hours_max": ("48", "Maximum hours to look back for sync"),
    "lookback_hours_default": ("24", "Default hours to look back for sync"),
    "default_recruiter_id": ("", "Default recruiter ID for new requisitions"),
    "email_from_address": ("noreply@company.com", "Email sender address"),
    "email_from_name": ("AIRecruiter", "Email sender name"),
    "s3_bucket": ("airecruiter-artifacts", "S3 bucket for artifacts"),
    "interview_token_expiry_days": ("7", "Days until interview token expires"),
}
