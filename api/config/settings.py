"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AIRecruiter v2"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"  # development, staging, production

    # Database (SQL Server)
    DATABASE_URL: str = "mssql+pyodbc://sa:password@localhost/airecruiter2?driver=ODBC+Driver+17+for+SQL+Server"

    # SSO / Authentication
    SSO_ENABLED: bool = True
    SSO_URL: str = "http://localhost:8000"  # centralized-auth URL
    SSO_APP_ID: str = "recruiter2"
    SSO_APP_SECRET: str = ""
    SSO_PUBLIC_KEY_PATH: Optional[str] = None  # Path to RS256 public key

    # Internal Token (HS256)
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours
    ALGORITHM: str = "HS256"

    # Cookie settings
    COOKIE_NAME: str = "recruiter2_access_token"
    COOKIE_DOMAIN: Optional[str] = None  # None = use request domain
    COOKIE_SECURE: bool = True  # HTTPS required
    COOKIE_SAMESITE: str = "lax"
    SECURE_COOKIES: bool = True  # Alias for compatibility

    # Workday
    WORKDAY_TENANT_URL: str = ""
    WORKDAY_TENANT_ID: str = ""
    WORKDAY_CLIENT_ID: str = ""
    WORKDAY_CLIENT_SECRET: str = ""  # Encrypted
    WORKDAY_REFRESH_TOKEN: str = ""  # Encrypted

    # Claude AI
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"

    # AWS S3 (separate credentials)
    S3_BUCKET: str = "airecruiter-artifacts"
    S3_PREFIX: str = "airecruiter2"
    S3_REGION: str = "us-west-2"
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None

    # AWS SES (separate credentials)
    SES_FROM_EMAIL: str = "jobs@ccfs.com"
    SES_FROM_NAME: str = "CCFS Talent Team"
    SES_REGION: str = "us-west-2"
    SES_ACCESS_KEY_ID: Optional[str] = None
    SES_SECRET_ACCESS_KEY: Optional[str] = None

    # Frontend URL (for interview links)
    FRONTEND_URL: str = "http://localhost:3000"

    # Encryption (Fernet key for credentials)
    ENCRYPTION_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def database_url_async(self) -> str:
        """Convert sync URL to async URL if needed."""
        # For SQL Server with pyodbc, we use sync driver
        # aioodbc is not well-maintained, so we use sync with run_in_executor
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
