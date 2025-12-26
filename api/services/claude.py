"""Claude AI client for API interview functionality.

Separate from the processor Claude client to avoid cross-package imports.
This client only handles interview response generation.
"""

from typing import List, Optional

import structlog
from anthropic import AsyncAnthropic, APIError

from api.config.settings import settings

logger = structlog.get_logger()


class ClaudeClient:
    """Claude AI client for interview response generation."""

    def __init__(self):
        """Initialize Claude client with async support."""
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = getattr(settings, "CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        self.max_tokens = getattr(settings, "CLAUDE_MAX_TOKENS", 16384)

    async def generate_interview_response(
        self,
        messages: List[dict],
        persona: str,
        context: str,
        redirect_triggers: Optional[List[str]] = None,
    ) -> str:
        """Generate an interview response.

        Args:
            messages: Conversation history [{"role": "user/assistant", "content": "..."}]
            persona: Interviewer persona description
            context: Job and candidate context
            redirect_triggers: Optional list of topics to redirect away from

        Returns:
            Assistant response text
        """
        logger.debug("Generating interview response")

        redirect_clause = ""
        if redirect_triggers:
            redirect_clause = f"""
If the candidate mentions any of these topics, acknowledge briefly and redirect to experience-focused questions:
{', '.join(redirect_triggers)}
"""

        system_prompt = f"""You are an AI interviewer conducting a job interview.

Persona: {persona}

Context: {context}

Guidelines:
- Be professional and friendly
- Ask follow-up questions based on responses
- Probe for specific examples and details
- Keep responses concise (2-3 sentences typically)
- Focus on job-related experience and skills
- After 8-10 exchanges, wrap up the interview naturally
{redirect_clause}
"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=messages,
            )

            return response.content[0].text

        except APIError as e:
            logger.error("Claude API error during interview", error=str(e))
            raise ClaudeError(f"Interview response generation failed: {str(e)}") from e


class ClaudeError(Exception):
    """Raised when Claude API calls fail."""

    pass
