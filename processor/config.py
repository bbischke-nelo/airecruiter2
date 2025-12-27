"""Processor configuration settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessorSettings(BaseSettings):
    """Settings for the processor service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "mssql+pyodbc://sa:password@localhost/airecruiter?driver=ODBC+Driver+17+for+SQL+Server"

    # Scheduler
    SCHEDULER_INTERVAL: int = 60  # Seconds between checks
    SCHEDULER_ENABLED: bool = True
    REQUISITION_SYNC_INTERVAL: int = 60  # Minutes between full requisition syncs

    # Sync filtering
    APPLICATION_MIN_DATE: Optional[str] = "2025-12-25"  # Don't sync applications before this date (YYYY-MM-DD)

    # Queue/Worker
    QUEUE_MAX_CONCURRENCY: int = 10  # Parallel job limit
    QUEUE_MAX_ATTEMPTS: int = 3  # Default retry limit
    QUEUE_POLL_INTERVAL: int = 5  # Seconds between queue checks when idle
    QUEUE_RETRY_BASE_DELAY: int = 30  # Base delay for exponential backoff (seconds)

    # Workday
    WORKDAY_TENANT_URL: str = "https://services1.wd503.myworkday.com"
    WORKDAY_TENANT_ID: str = "ccfs"
    WORKDAY_TENANT: str = "ccfs"  # Alias for TENANT_ID
    WORKDAY_API_VERSION: str = "v42.0"
    WORKDAY_CLIENT_ID: Optional[str] = None
    WORKDAY_CLIENT_SECRET: Optional[str] = None
    WORKDAY_REFRESH_TOKEN: Optional[str] = None

    # Claude AI
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"
    CLAUDE_MAX_TOKENS: int = 16384

    # S3
    S3_BUCKET: str = "airecruiter-artifacts"
    S3_REGION: str = "us-east-1"
    S3_PREFIX: str = "v2/"

    # Email (SES)
    SES_FROM_EMAIL: str = "noreply@example.com"
    SES_FROM_NAME: str = "AIRecruiter"
    SES_REGION: str = "us-east-1"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Monitoring
    HEARTBEAT_INTERVAL: int = 30  # Seconds between heartbeat writes
    HEARTBEAT_FILE: str = "/tmp/airecruiter_heartbeat"

    # Encryption (for credentials)
    ENCRYPTION_KEY: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


@lru_cache
def get_settings() -> ProcessorSettings:
    """Get cached settings instance."""
    return ProcessorSettings()


settings = get_settings()
