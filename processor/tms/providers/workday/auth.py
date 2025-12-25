"""Workday OAuth2 authentication handler."""

import time
from typing import Optional

import httpx
import structlog

from .config import WorkdayConfig

logger = structlog.get_logger()


class WorkdayAuth:
    """Handles Workday OAuth2 token management."""

    def __init__(self, config: WorkdayConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._refresh_token: str = config.refresh_token

    @property
    def access_token(self) -> Optional[str]:
        """Get current access token if still valid."""
        if self._access_token and time.time() < self._token_expires_at - self.config.token_refresh_threshold:
            return self._access_token
        return None

    async def get_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            WorkdayAuthError: If token refresh fails
        """
        # Check if current token is still valid
        if self.access_token:
            return self._access_token

        # Need to refresh
        await self._refresh_access_token()
        return self._access_token

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token."""
        logger.info("Refreshing Workday access token")

        async with httpx.AsyncClient(timeout=self.config.connect_timeout) as client:
            try:
                response = await client.post(
                    self.config.oauth_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                response.raise_for_status()
                data = response.json()

                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in

                # Update refresh token if a new one was provided
                if "refresh_token" in data:
                    self._refresh_token = data["refresh_token"]

                logger.info(
                    "Workday access token refreshed",
                    expires_in=expires_in,
                )

            except httpx.HTTPStatusError as e:
                logger.error(
                    "Workday token refresh failed",
                    status_code=e.response.status_code,
                    response=e.response.text[:500],
                )
                raise WorkdayAuthError(f"Token refresh failed: {e.response.status_code}") from e

            except Exception as e:
                logger.error("Workday token refresh error", error=str(e))
                raise WorkdayAuthError(f"Token refresh error: {str(e)}") from e

    def invalidate_token(self) -> None:
        """Invalidate the current access token to force refresh."""
        self._access_token = None
        self._token_expires_at = 0


class WorkdayAuthError(Exception):
    """Raised when Workday authentication fails."""

    pass
