"""Claude AI client for API endpoints (interview WebSocket)."""

import structlog
from anthropic import Anthropic, APIError

from api.config.settings import settings

logger = structlog.get_logger()


class ClaudeClient:
    """Simple Claude client for interview responses."""

    def __init__(self):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL


class ClaudeError(Exception):
    """Raised when Claude API calls fail."""

    pass
