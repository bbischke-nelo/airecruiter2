"""Workday configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkdayConfig:
    """Configuration for Workday SOAP API access."""

    # Tenant configuration
    tenant_url: str  # e.g., https://services1.wd503.myworkday.com
    tenant_id: str  # e.g., ccfs

    # OAuth credentials
    client_id: str
    client_secret: str
    refresh_token: str

    # API settings
    api_version: str = "v43.2"

    # Rate limiting
    rate_limit_delay: float = 0.1  # 100ms = max 10 calls/second

    # Retry settings
    max_retries: int = 3
    retry_backoff: float = 2.0

    # Timeouts
    connect_timeout: int = 30
    read_timeout: int = 60

    # Cache settings
    token_refresh_threshold: int = 300  # Refresh token if <5 min remaining

    @property
    def oauth_url(self) -> str:
        """Get OAuth token endpoint URL."""
        return f"{self.tenant_url}/ccx/oauth2/{self.tenant_id}/token"

    @property
    def recruiting_wsdl_url(self) -> str:
        """Get Recruiting WSDL URL."""
        return f"{self.tenant_url}/ccx/service/{self.tenant_id}/Recruiting/{self.api_version}?wsdl"

    @property
    def recruiting_service_url(self) -> str:
        """Get Recruiting service URL."""
        return f"{self.tenant_url}/ccx/service/{self.tenant_id}/Recruiting/{self.api_version}"

    @property
    def integrations_wsdl_url(self) -> str:
        """Get Integrations WSDL URL (for Get_References)."""
        return f"{self.tenant_url}/ccx/service/{self.tenant_id}/Integrations/{self.api_version}?wsdl"

    @property
    def integrations_service_url(self) -> str:
        """Get Integrations service URL."""
        return f"{self.tenant_url}/ccx/service/{self.tenant_id}/Integrations/{self.api_version}"
