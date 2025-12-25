"""Claude AI integration for resume analysis and interview evaluation."""

import json
import re
from dataclasses import dataclass
from string import Template
from typing import List, Optional

import structlog
from anthropic import Anthropic, APIError

from processor.config import settings

logger = structlog.get_logger()


def safe_template_substitute(template: str, **kwargs) -> str:
    """Safely substitute template variables without crashing on special chars.

    Uses string.Template which handles $variable syntax and doesn't crash
    on curly braces in user content. Falls back to simple replacement.

    Args:
        template: Template string with {variable} or $variable placeholders
        **kwargs: Variable values to substitute

    Returns:
        Substituted string
    """
    # First convert {var} syntax to $var for Template compatibility
    # But preserve {{ and }} as literal braces
    converted = template.replace("{{", "__DOUBLE_OPEN__").replace("}}", "__DOUBLE_CLOSE__")

    # Convert {name} to ${name} for Template
    converted = re.sub(r'\{(\w+)\}', r'${\1}', converted)

    # Restore literal braces
    converted = converted.replace("__DOUBLE_OPEN__", "{").replace("__DOUBLE_CLOSE__", "}")

    try:
        return Template(converted).safe_substitute(**kwargs)
    except Exception:
        # Ultimate fallback: just do simple string replacement
        result = template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result


@dataclass
class AnalysisResult:
    """Result of resume analysis."""

    risk_score: int  # 1-10 scale
    relevance_summary: str
    pros: List[str]
    cons: List[str]
    red_flags: List[str]
    suggested_questions: List[str]
    raw_response: str


@dataclass
class EvaluationResult:
    """Result of interview evaluation.

    Matches v1 evaluation schema with character gate, retention risk, etc.
    """

    # Scores (1-5 scale per v1)
    reliability_score: int
    accountability_score: int
    professionalism_score: int
    communication_score: int
    technical_score: int
    growth_potential_score: int

    # Summary and lists
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    red_flags: List[str]

    # v1 specific fields
    character_passed: bool  # Character gate pass/fail
    retention_risk: str  # LOW, MEDIUM, HIGH
    authenticity_assessment: str  # PASS, FAIL, REVIEW
    readiness: str  # READY, NEEDS SUPPORT, NEEDS DEVELOPMENT
    next_interview_focus: List[str]  # Follow-up questions for hiring manager

    # Recommendation: interview (4-5), review (3), decline (0-2)
    recommendation: str

    raw_response: str


class ClaudeClient:
    """Client for Claude AI API."""

    def __init__(self):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.CLAUDE_MAX_TOKENS

    async def analyze_resume(
        self,
        resume_text: str,
        job_description: str,
        prompt_template: str,
    ) -> AnalysisResult:
        """Analyze a resume against job requirements.

        Args:
            resume_text: Extracted text from resume
            job_description: Full job description/requirements
            prompt_template: Analysis prompt template

        Returns:
            AnalysisResult with scores and insights
        """
        logger.info("Analyzing resume with Claude")

        # Build the prompt using safe substitution to handle special chars in resume
        prompt = safe_template_substitute(
            prompt_template,
            resume=resume_text,
            job_description=job_description,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            raw_response = response.content[0].text

            # Parse the structured response
            result = self._parse_analysis_response(raw_response)

            logger.info(
                "Resume analysis complete",
                risk_score=result.risk_score,
                pros_count=len(result.pros),
                cons_count=len(result.cons),
            )

            return result

        except APIError as e:
            logger.error("Claude API error during analysis", error=str(e))
            raise ClaudeError(f"Resume analysis failed: {str(e)}") from e

    async def evaluate_interview(
        self,
        transcript: str,
        prompt_template: str,
    ) -> EvaluationResult:
        """Evaluate a completed interview.

        Args:
            transcript: Full interview transcript
            prompt_template: Evaluation prompt template

        Returns:
            EvaluationResult with scores and insights
        """
        logger.info("Evaluating interview with Claude")

        # Build the prompt using safe substitution to handle special chars in transcript
        prompt = safe_template_substitute(prompt_template, transcript=transcript)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            raw_response = response.content[0].text

            # Parse the structured response
            result = self._parse_evaluation_response(raw_response)

            logger.info(
                "Interview evaluation complete",
                overall_score=(
                    result.reliability_score +
                    result.accountability_score +
                    result.professionalism_score +
                    result.communication_score +
                    result.technical_score +
                    result.growth_potential_score
                ) / 6,
                recommendation=result.recommendation,
            )

            return result

        except APIError as e:
            logger.error("Claude API error during evaluation", error=str(e))
            raise ClaudeError(f"Interview evaluation failed: {str(e)}") from e

    async def generate_interview_response(
        self,
        messages: List[dict],
        persona: str,
        context: str,
    ) -> str:
        """Generate an interview response.

        Args:
            messages: Conversation history [{"role": "user/assistant", "content": "..."}]
            persona: Interviewer persona description
            context: Job and candidate context

        Returns:
            Assistant response text
        """
        logger.debug("Generating interview response")

        system_prompt = f"""You are an AI interviewer conducting a job interview.

Persona: {persona}

Context: {context}

Guidelines:
- Be professional and friendly
- Ask follow-up questions based on responses
- Probe for specific examples and details
- Keep responses concise (2-3 sentences typically)
- After 8-10 exchanges, wrap up the interview naturally
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=messages,
            )

            return response.content[0].text

        except APIError as e:
            logger.error("Claude API error during interview", error=str(e))
            raise ClaudeError(f"Interview response generation failed: {str(e)}") from e

    def _parse_analysis_response(self, response: str) -> AnalysisResult:
        """Parse analysis response from Claude.

        Expected format: JSON with specific fields.
        """
        try:
            # Try to extract JSON from response
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            return AnalysisResult(
                risk_score=int(data.get("risk_score", 5)),
                relevance_summary=data.get("relevance_summary", ""),
                pros=data.get("pros", []),
                cons=data.get("cons", []),
                red_flags=data.get("red_flags", []),
                suggested_questions=data.get("suggested_questions", []),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse analysis response", error=str(e))
            # Return a default result with the raw response
            return AnalysisResult(
                risk_score=5,
                relevance_summary="Unable to parse structured response",
                pros=[],
                cons=[],
                red_flags=[],
                suggested_questions=[],
                raw_response=response,
            )

    def _parse_evaluation_response(self, response: str) -> EvaluationResult:
        """Parse evaluation response from Claude.

        Expected format: JSON with v1 evaluation schema fields.
        """
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            # Parse character gate - can be bool or string
            character_passed = data.get("character_passed", True)
            if isinstance(character_passed, str):
                character_passed = character_passed.lower() in ("true", "pass", "yes")

            return EvaluationResult(
                # Scores (1-5 scale)
                reliability_score=int(data.get("reliability_score", 3)),
                accountability_score=int(data.get("accountability_score", 3)),
                professionalism_score=int(data.get("professionalism_score", 3)),
                communication_score=int(data.get("communication_score", 3)),
                technical_score=int(data.get("technical_score", 3)),
                growth_potential_score=int(data.get("growth_potential_score", 3)),
                # Summary and lists
                summary=data.get("summary", ""),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                red_flags=data.get("red_flags", []),
                # v1 specific fields
                character_passed=character_passed,
                retention_risk=data.get("retention_risk", "MEDIUM"),
                authenticity_assessment=data.get("authenticity_assessment", "PASS"),
                readiness=data.get("readiness", "NEEDS SUPPORT"),
                next_interview_focus=data.get("next_interview_focus", []),
                # Recommendation
                recommendation=data.get("recommendation", "review"),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse evaluation response", error=str(e))
            return EvaluationResult(
                reliability_score=3,
                accountability_score=3,
                professionalism_score=3,
                communication_score=3,
                technical_score=3,
                growth_potential_score=3,
                summary="Unable to parse structured response",
                strengths=[],
                weaknesses=[],
                red_flags=[],
                character_passed=True,
                retention_risk="MEDIUM",
                authenticity_assessment="REVIEW",
                readiness="NEEDS SUPPORT",
                next_interview_focus=[],
                recommendation="review",
                raw_response=response,
            )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from a response that may contain other text."""
        # Look for JSON object
        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end > start:
            return text[start:end]

        # Look for JSON array
        start = text.find("[")
        end = text.rfind("]") + 1

        if start != -1 and end > start:
            return text[start:end]

        raise ValueError("No JSON found in response")


class ClaudeError(Exception):
    """Raised when Claude API calls fail."""

    pass
