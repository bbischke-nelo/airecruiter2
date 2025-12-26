"""Claude AI integration for resume fact extraction and interview summarization.

Human-in-the-Loop Pipeline: AI extracts facts only, NO scoring or recommendations.
All hiring decisions are made by human recruiters.
"""

import json
import re
from dataclasses import dataclass, field
from string import Template
from typing import Dict, List, Optional, Any

import structlog
from anthropic import Anthropic, APIError

from processor.config import settings

logger = structlog.get_logger()


def safe_template_substitute(template: str, **kwargs) -> str:
    """Safely substitute template variables without crashing on special chars.

    Uses string.Template which handles $variable syntax and doesn't crash
    on curly braces in user content. Falls back to simple replacement.
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
class FactExtractionResult:
    """Result of resume fact extraction.

    Contains only factual information - NO scores, rankings, or recommendations.
    Human recruiters make all hiring decisions.
    """

    extraction_version: str = "1.0"

    # Employment history
    employment_history: List[Dict[str, Any]] = field(default_factory=list)
    # [{"employer": "...", "title": "...", "start_date": "...", "end_date": "...", "duration_months": 0, "responsibilities": [...]}]

    # Skills
    skills: Dict[str, List[str]] = field(default_factory=dict)
    # {"technical": [...], "software": [...], "industry_specific": [...]}

    # Certifications
    certifications: List[Dict[str, Any]] = field(default_factory=list)
    # [{"name": "...", "issuer": "...", "date_obtained": "...", "expiry": "..."}]

    # Education
    education: List[Dict[str, Any]] = field(default_factory=list)
    # [{"institution": "...", "degree": "...", "field": "...", "graduation_date": "..."}]

    # Logistics (work eligibility, location, etc.)
    logistics: Dict[str, Any] = field(default_factory=dict)

    # Timeline (for visualizing career progression)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    # Summary statistics
    summary_stats: Dict[str, Any] = field(default_factory=dict)
    # {"total_experience_months": 0, "employers_count": 0, "average_tenure_months": 0}

    # JD requirements match (semantic matching, not keyword matching)
    jd_requirements_match: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "requirements": [{"requirement": "...", "category": "...", "met": "yes|no|partial", "evidence": "...", "explanation": "..."}],
    #   "summary": {"total_requirements": 0, "fully_met": 0, "partially_met": 0, "not_met": 0, "match_percentage": 0}
    # }

    # Observations (factual, tied to JD requirements)
    observations: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    # {"pros": [{"category": "...", "observation": "...", "evidence": "..."}], "cons": [...], "suggested_questions": [...]}

    # Factual summary
    relevance_summary: Optional[str] = None

    # Raw AI response for debugging
    raw_response: str = ""


@dataclass
class AnalysisResult:
    """Result of resume analysis (legacy format for backward compatibility).

    Used by AnalyzeProcessor for risk scoring.
    """

    risk_score: int = 5  # 1-10 scale, 10 = highest risk/least qualified
    relevance_summary: str = ""
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    suggested_questions: List[str] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class InterviewSummaryResult:
    """Result of interview summarization.

    Contains only factual summary - NO scores, rankings, or recommendations.
    Human recruiters make all hiring decisions.
    """

    # Factual summary of interview
    summary: str = ""

    # Key highlights from interview (factual observations)
    highlights: List[Dict[str, str]] = field(default_factory=list)
    # [{"topic": "...", "observation": "...", "quote": "..."}]

    # Topics covered
    topics_covered: List[str] = field(default_factory=list)

    # Areas to explore in live interview
    follow_up_areas: List[Dict[str, str]] = field(default_factory=list)
    # [{"topic": "...", "reason": "...", "suggested_question": "..."}]

    # Candidate's stated preferences
    candidate_preferences: Dict[str, Any] = field(default_factory=dict)

    # Raw AI response for debugging
    raw_response: str = ""


class ClaudeClient:
    """Client for Claude AI API.

    Human-in-the-Loop: Extracts facts and summarizes interviews.
    Does NOT score, rank, or make recommendations.
    """

    def __init__(self):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self.max_tokens = settings.CLAUDE_MAX_TOKENS

    async def extract_facts(
        self,
        resume_text: str,
        job_description: str,
        prompt_template: str,
        candidate_id: Optional[str] = None,
        application_date: Optional[str] = None,
        # Additional context parameters
        requisition_title: Optional[str] = None,
        role_level: Optional[str] = None,
        location: Optional[str] = None,
        application_source: Optional[str] = None,
        workday_profile: Optional[dict] = None,
    ) -> FactExtractionResult:
        """Extract factual information from a resume.

        NO scoring, ranking, or recommendations - only facts.

        Args:
            resume_text: Extracted text from resume
            job_description: Full job description/requirements
            prompt_template: Fact extraction prompt template
            candidate_id: Optional candidate identifier for logging
            application_date: Optional application date for context
            requisition_title: Position title
            role_level: Level of role (IC, Manager, etc.)
            location: Job location
            application_source: Where candidate applied from
            workday_profile: Candidate profile data from Workday (work history, education, skills)

        Returns:
            FactExtractionResult with extracted facts
        """
        logger.info("Extracting facts from resume with Claude", candidate_id=candidate_id)

        # Build Workday profile context if available
        workday_context = ""
        if workday_profile:
            workday_context = "\n## Workday Profile Data\n"
            if workday_profile.get("work_history"):
                workday_context += "Work History:\n"
                for job in workday_profile["work_history"][:5]:
                    title = job.get("title", "Unknown")
                    company = job.get("company", "Unknown")
                    start = job.get("start_date", "?")
                    end = job.get("end_date", "Present")
                    workday_context += f"- {title} at {company} ({start} - {end})\n"
            if workday_profile.get("education"):
                workday_context += "Education:\n"
                for edu in workday_profile["education"][:3]:
                    degree = edu.get("degree", "Degree")
                    school = edu.get("school", "Unknown")
                    workday_context += f"- {degree} from {school}\n"
            if workday_profile.get("skills"):
                workday_context += f"Skills: {', '.join(workday_profile['skills'][:15])}\n"

        # Build the prompt using safe substitution
        prompt = safe_template_substitute(
            prompt_template,
            resume=resume_text,
            job_description=job_description,
            application_date=application_date or "Not provided",
            requisition_title=requisition_title or "Not specified",
            role_level=role_level or "Not specified",
            location=location or "Not specified",
            application_source=application_source or "Unknown",
            workday_profile=workday_context or "No Workday profile data available",
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
            result = self._parse_fact_extraction_response(raw_response)

            logger.info(
                "Fact extraction complete",
                candidate_id=candidate_id,
                employers_count=len(result.employment_history),
                skills_count=len(result.skills.get("technical", [])),
            )

            return result

        except APIError as e:
            logger.error("Claude API error during fact extraction", error=str(e))
            raise ClaudeError(f"Fact extraction failed: {str(e)}") from e

    async def analyze_resume(
        self,
        resume_text: str,
        job_description: str,
        prompt_template: str,
    ) -> AnalysisResult:
        """Analyze a resume against job requirements.

        Legacy method for backward compatibility with AnalyzeProcessor.
        Returns risk score and categorized observations.

        Args:
            resume_text: Extracted text from resume
            job_description: Full job description/requirements
            prompt_template: Analysis prompt template

        Returns:
            AnalysisResult with risk score and observations
        """
        logger.info("Analyzing resume with Claude")

        # Build the prompt using safe substitution
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
            logger.error("Claude API error during resume analysis", error=str(e))
            raise ClaudeError(f"Resume analysis failed: {str(e)}") from e

    async def summarize_interview(
        self,
        transcript: str,
        prompt_template: str,
        job_description: Optional[str] = None,
    ) -> InterviewSummaryResult:
        """Summarize a completed interview.

        NO scoring, ranking, or recommendations - only factual summary.

        Args:
            transcript: Full interview transcript
            prompt_template: Summary prompt template
            job_description: Optional job description for context

        Returns:
            InterviewSummaryResult with factual summary
        """
        logger.info("Summarizing interview with Claude")

        # Build the prompt using safe substitution
        prompt = safe_template_substitute(
            prompt_template,
            transcript=transcript,
            job_description=job_description or "Not provided",
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
            result = self._parse_interview_summary_response(raw_response)

            logger.info(
                "Interview summary complete",
                highlights_count=len(result.highlights),
                topics_count=len(result.topics_covered),
            )

            return result

        except APIError as e:
            logger.error("Claude API error during interview summary", error=str(e))
            raise ClaudeError(f"Interview summary failed: {str(e)}") from e

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

    def _parse_fact_extraction_response(self, response: str) -> FactExtractionResult:
        """Parse fact extraction response from Claude."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            return FactExtractionResult(
                extraction_version=data.get("extraction_version", "1.0"),
                employment_history=data.get("employment_history", []),
                skills=data.get("skills", {}),
                certifications=data.get("certifications", []),
                education=data.get("education", []),
                logistics=data.get("logistics", {}),
                timeline=data.get("timeline", []),
                summary_stats=data.get("summary_stats", {}),
                jd_requirements_match=data.get("jd_requirements_match", {}),
                observations=data.get("observations", {}),
                relevance_summary=data.get("relevance_summary"),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse fact extraction response", error=str(e))
            return FactExtractionResult(
                relevance_summary="Unable to parse structured response",
                raw_response=response,
            )

    def _parse_interview_summary_response(self, response: str) -> InterviewSummaryResult:
        """Parse interview summary response from Claude."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            return InterviewSummaryResult(
                summary=data.get("summary", ""),
                highlights=data.get("highlights", []),
                topics_covered=data.get("topics_covered", []),
                follow_up_areas=data.get("follow_up_areas", []),
                candidate_preferences=data.get("candidate_preferences", {}),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse interview summary response", error=str(e))
            return InterviewSummaryResult(
                summary="Unable to parse structured response",
                raw_response=response,
            )

    def _parse_analysis_response(self, response: str) -> AnalysisResult:
        """Parse resume analysis response from Claude."""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            # Handle risk_score - ensure it's an int between 1-10
            risk_score = data.get("risk_score", 5)
            if isinstance(risk_score, str):
                risk_score = int(risk_score)
            risk_score = max(1, min(10, risk_score))

            return AnalysisResult(
                risk_score=risk_score,
                relevance_summary=data.get("relevance_summary", ""),
                pros=data.get("pros", []),
                cons=data.get("cons", []),
                red_flags=data.get("red_flags", []),
                suggested_questions=data.get("suggested_questions", []),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse analysis response", error=str(e))
            return AnalysisResult(
                risk_score=5,
                relevance_summary="Unable to parse structured response",
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
