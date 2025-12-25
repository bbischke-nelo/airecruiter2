"""TMS service for managing TMS provider connections."""

import json
from typing import Optional

import structlog
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.config import settings
from processor.tms.base import TMSProvider
from processor.tms.providers.workday import WorkdayProvider, WorkdayConfig

logger = structlog.get_logger()


class TMSService:
    """Service for managing TMS provider connections."""

    def __init__(self, db: Session):
        """Initialize TMS service.

        Args:
            db: Database session
        """
        self.db = db
        self._provider: Optional[TMSProvider] = None
        self._fernet: Optional[Fernet] = None

        # Initialize encryption if key is available
        if settings.ENCRYPTION_KEY:
            self._fernet = Fernet(settings.ENCRYPTION_KEY.encode())

    async def get_provider(self) -> TMSProvider:
        """Get or create TMS provider instance.

        Returns:
            Initialized TMS provider

        Raises:
            TMSServiceError: If credentials not configured or invalid
        """
        if self._provider:
            return self._provider

        # Load credentials from database
        credentials = await self._load_credentials()

        if not credentials:
            raise TMSServiceError("TMS credentials not configured")

        # Create provider based on provider type
        provider_type = credentials.get("provider_type", "workday")

        if provider_type == "workday":
            config = WorkdayConfig(
                tenant_url=credentials.get("tenant_url", settings.WORKDAY_TENANT_URL),
                tenant_id=credentials.get("tenant_id", settings.WORKDAY_TENANT_ID),
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"],
                refresh_token=credentials["refresh_token"],
                api_version=credentials.get("api_version", settings.WORKDAY_API_VERSION),
            )
            self._provider = WorkdayProvider(config)
        else:
            raise TMSServiceError(f"Unknown provider type: {provider_type}")

        # Initialize the provider
        await self._provider.initialize()

        logger.info("TMS provider initialized", provider=provider_type)
        return self._provider

    async def close(self) -> None:
        """Close the TMS provider connection."""
        if self._provider:
            await self._provider.close()
            self._provider = None

    async def _load_credentials(self) -> Optional[dict]:
        """Load TMS credentials from database."""
        query = text("""
            SELECT client_id, client_secret, refresh_token,
                   tenant_url, tenant_id
            FROM credentials
            WHERE is_valid = 1
            ORDER BY updated_at DESC
        """)

        result = self.db.execute(query)
        row = result.fetchone()

        if not row:
            return None

        # Decrypt secrets if encrypted
        client_secret = self._decrypt(row.client_secret) if row.client_secret else None
        refresh_token = self._decrypt(row.refresh_token) if row.refresh_token else None

        return {
            "provider_type": "workday",
            "client_id": row.client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "tenant_url": row.tenant_url,
            "tenant_id": row.tenant_id,
            "api_version": settings.WORKDAY_API_VERSION,
        }

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted value.

        Args:
            encrypted_value: Fernet-encrypted value

        Returns:
            Decrypted string
        """
        if not self._fernet:
            # If no encryption key, assume value is not encrypted
            logger.warning("No encryption key configured, assuming unencrypted value")
            return encrypted_value

        try:
            return self._fernet.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            logger.error("Failed to decrypt value", error=str(e))
            raise TMSServiceError("Failed to decrypt credentials") from e

    async def test_connection(self) -> dict:
        """Test TMS connection.

        Returns:
            Health status dictionary
        """
        try:
            provider = await self.get_provider()
            health = await provider.health_check()
            return {
                "healthy": health.healthy,
                "message": health.message,
                "details": health.details,
            }
        except Exception as e:
            logger.error("TMS connection test failed", error=str(e))
            return {
                "healthy": False,
                "message": str(e),
                "details": {},
            }


class TMSServiceError(Exception):
    """Raised when TMS service operations fail."""

    pass
