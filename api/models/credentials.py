"""Credential model for Workday OAuth2 credentials."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy import func

from api.config.database import Base


class Credential(Base):
    """
    Workday OAuth2 credentials.

    Encrypted fields: client_secret, refresh_token
    """

    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Workday connection
    tenant_url = Column(String(500), nullable=False)  # https://services1.wd503.myworkday.com
    tenant_id = Column(String(100), nullable=False, unique=True)  # ccfs
    client_id = Column(String(255), nullable=False)
    client_secret = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted

    # Status
    is_valid = Column(Boolean, default=False)
    last_validated = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=func.getutcdate())
    updated_at = Column(DateTime, onupdate=func.getutcdate())

    def __repr__(self) -> str:
        return f"<Credential(tenant_id={self.tenant_id}, is_valid={self.is_valid})>"
