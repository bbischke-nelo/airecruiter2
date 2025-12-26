"""Shared interview service for both public and proxy interviews.

This service contains the core interview logic that is shared between:
- Public self-service interviews (candidate via token link)
- Proxy interviews (recruiter conducting on candidate's behalf)
"""

import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import structlog
from sqlalchemy.orm import Session

from api.models import Interview, Message, Application, Requisition, Persona, Analysis, CandidateProfile
from processor.integrations.claude import ClaudeClient

logger = structlog.get_logger()


class InterviewService:
    """Shared interview logic for public and proxy interviews."""

    def __init__(self, db: Session):
        self.db = db
        self.claude = ClaudeClient()

    async def start_interview(
        self,
        interview_id: int,
        interview_type: str = "self_service",
    ) -> Message:
        """Start an interview and generate the initial greeting.

        Args:
            interview_id: Interview to start
            interview_type: 'self_service' or 'proxy'

        Returns:
            Initial greeting message
        """
        interview = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # Get context
        application = interview.application
        requisition = application.requisition
        candidate_name = application.candidate_name
        position_title = requisition.name

        # Generate greeting based on interview type
        if interview_type == "proxy":
            greeting = self._generate_proxy_greeting(candidate_name, position_title)
        else:
            greeting = self._generate_self_service_greeting(candidate_name, position_title)

        # Update status and save greeting in single transaction
        interview.status = "in_progress"
        interview.started_at = datetime.now(timezone.utc)

        message = Message(
            interview_id=interview_id,
            role="assistant",
            content=greeting,
        )
        self.db.add(message)

        # Commit both status update and greeting atomically
        self.db.commit()
        self.db.refresh(message)

        logger.info(
            "Interview started",
            interview_id=interview_id,
            interview_type=interview_type,
        )

        return message

    async def process_message(
        self,
        interview_id: int,
        user_message: str,
    ) -> tuple[Message, Message]:
        """Process a user message and generate AI response.

        Args:
            interview_id: Interview ID
            user_message: Content from user (or typed by recruiter for proxy)

        Returns:
            Tuple of (user_message, ai_response)
        """
        interview = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        application = interview.application
        requisition = application.requisition

        # Save user message
        user_msg = Message(
            interview_id=interview_id,
            role="user",
            content=user_message,
        )
        self.db.add(user_msg)
        self.db.commit()
        self.db.refresh(user_msg)

        # Get conversation history
        messages = self._get_conversation_history(interview_id)

        # Build context
        persona_description = self._get_persona_description(interview.persona)
        context = self._build_context(
            interview=interview,
            application=application,
            requisition=requisition,
        )

        # Generate AI response
        try:
            ai_response_text = await self.claude.generate_interview_response(
                messages=messages,
                persona=persona_description,
                context=context,
            )
        except Exception as e:
            logger.error("Failed to generate AI response", error=str(e))
            ai_response_text = "I apologize, but I'm experiencing a technical issue. Could you please repeat that?"

        # Save AI response
        ai_msg = Message(
            interview_id=interview_id,
            role="assistant",
            content=ai_response_text,
        )
        self.db.add(ai_msg)
        self.db.commit()
        self.db.refresh(ai_msg)

        # Check if interview should complete (after 8-10 exchanges)
        message_count = len(messages) + 2  # Including the ones we just added
        if self._should_complete_interview(ai_response_text, message_count):
            interview.status = "completed"
            interview.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info("Interview completed", interview_id=interview_id)

        return user_msg, ai_msg

    async def end_interview(self, interview_id: int) -> Interview:
        """Manually end an interview.

        Args:
            interview_id: Interview to end

        Returns:
            Updated interview
        """
        interview = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        interview.status = "completed"
        interview.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(interview)

        logger.info("Interview ended manually", interview_id=interview_id)

        return interview

    def _generate_proxy_greeting(self, candidate_name: str, position_title: str) -> str:
        """Generate greeting for recruiter-conducted proxy interview.

        Uses 3rd person framing since recruiter is typing on candidate's behalf.
        """
        return f"""Ready to begin the interview for {candidate_name} applying for the {position_title} position.

I'll be asking questions about {candidate_name}'s experience and qualifications. Please type their responses as they share them with you.

Let's start: What is {candidate_name}'s current role? Can you describe what they do day-to-day and what they're responsible for?"""

    def _generate_self_service_greeting(self, candidate_name: str, position_title: str) -> str:
        """Generate greeting for self-service candidate interview."""
        # Use first name only
        first_name = candidate_name.split()[0] if candidate_name else "there"

        return f"""Hello {first_name}! Thank you for taking the time to interview for the {position_title} position.

I'm here to learn more about your experience and qualifications. This interview should take about 10-15 minutes.

Let's get started - can you tell me a bit about yourself and what interests you about this role?"""

    def _get_persona_description(self, persona: Optional[Persona]) -> str:
        """Get persona description for AI context."""
        if persona and persona.system_prompt:
            return persona.system_prompt

        return """You are a professional recruiter conducting a job interview.
Be friendly but focused on job-relevant qualifications.
Ask follow-up questions to get specific examples."""

    def _build_context(
        self,
        interview: Interview,
        application: Application,
        requisition: Requisition,
    ) -> str:
        """Build context string for AI response generation.

        Includes:
        - Position and job description
        - Candidate information and application metadata
        - Resume analysis insights (pros, cons, suggested questions)
        - Candidate profile from Workday (work history, education, skills)
        """
        interview_type = interview.interview_type
        candidate_name = application.candidate_name

        # Build position context
        context = f"""## Position Information
Position: {requisition.name}
"""
        if hasattr(requisition, "role_level") and requisition.role_level:
            context += f"Role Level: {requisition.role_level}\n"
        if hasattr(requisition, "location") and requisition.location:
            context += f"Location: {requisition.location}\n"

        # Build candidate context
        context += f"""
## Candidate Information
Name: {candidate_name}
"""
        if hasattr(application, "applied_at") and application.applied_at:
            context += f"Applied: {application.applied_at.strftime('%Y-%m-%d') if hasattr(application.applied_at, 'strftime') else application.applied_at}\n"
        if hasattr(application, "application_source") and application.application_source:
            context += f"Source: {application.application_source}\n"

        # Add job description
        if requisition.detailed_description:
            context += f"\n## Job Description\n{requisition.detailed_description[:1500]}\n"

        # Load and add analysis insights
        analysis = self.db.query(Analysis).filter(
            Analysis.application_id == application.id
        ).first()

        if analysis:
            context += self._format_analysis_context(analysis)

        # Load and add candidate profile
        if hasattr(application, "candidate_profile") and application.candidate_profile:
            context += self._format_profile_context(application.candidate_profile)

        # Add proxy mode context if applicable
        if interview_type == "proxy":
            context += f"""
## INTERVIEW MODE: RECRUITER-ASSISTED (Proxy)
IMPORTANT: The recruiter is typing the candidate's responses as they speak with the candidate.
Frame ALL questions in THIRD PERSON about the candidate ({candidate_name}).
Examples:
- Instead of "Tell me about your experience" → "What is {candidate_name}'s experience?"
- Instead of "Why are you interested?" → "Why is {candidate_name} interested in this role?"
- Instead of "What are your strengths?" → "What would {candidate_name} say are their strengths?"
"""
        else:
            context += "\n## INTERVIEW MODE: Self-Service\nSpeak directly to the candidate in a friendly, professional manner.\n"

        return context

    def _safe_parse_json(self, data) -> list:
        """Safely parse JSON strings or return lists."""
        if not data:
            return []
        if isinstance(data, list):
            return data
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return []

    def _format_analysis_context(self, analysis: Analysis) -> str:
        """Format resume analysis data for interview context."""
        sections = ["\n## Resume Analysis Insights"]

        if analysis.relevance_summary:
            sections.append(f"\nSummary: {analysis.relevance_summary}")

        pros = self._safe_parse_json(analysis.pros)
        if pros:
            sections.append("\nStrengths:")
            for p in pros[:5]:
                sections.append(f"- {p}")

        cons = self._safe_parse_json(analysis.cons)
        if cons:
            sections.append("\nGaps/Areas to Probe:")
            for c in cons[:5]:
                sections.append(f"- {c}")

        red_flags = self._safe_parse_json(getattr(analysis, "red_flags", None))
        if red_flags:
            sections.append("\nRed Flags to Address:")
            for f in red_flags[:3]:
                sections.append(f"- {f}")

        suggested_questions = self._safe_parse_json(analysis.suggested_questions)
        if suggested_questions:
            sections.append("\nSuggested Questions from Resume Review:")
            for q in suggested_questions[:5]:
                sections.append(f"- {q}")

        return "\n".join(sections)

    def _format_profile_context(self, profile: CandidateProfile) -> str:
        """Format candidate profile data for interview context."""
        sections = ["\n## Candidate Profile (from Workday)"]

        # Work history
        work_history = self._safe_parse_json(profile.work_history)
        if work_history:
            sections.append("\nRecent Work History:")
            for job in work_history[:3]:
                title = job.get("title", "Unknown Role")
                company = job.get("company", "Unknown Company")
                start = job.get("start_date", "?")[:7] if job.get("start_date") else "?"
                end = job.get("end_date", "Present")[:7] if job.get("end_date") else "Present"
                sections.append(f"- {title} at {company} ({start} - {end})")

        # Education
        education = self._safe_parse_json(profile.education)
        if education:
            sections.append("\nEducation:")
            for edu in education[:2]:
                degree = edu.get("degree", "Degree")
                school = edu.get("school", "Unknown School")
                field = edu.get("field", "")
                field_str = f" in {field}" if field else ""
                sections.append(f"- {degree}{field_str} from {school}")

        # Skills
        skills = self._safe_parse_json(profile.skills)
        if skills:
            sections.append(f"\nSkills: {', '.join(skills[:10])}")

        return "\n".join(sections)

    def _get_conversation_history(self, interview_id: int) -> List[Dict[str, str]]:
        """Get conversation history in Claude message format."""
        messages = (
            self.db.query(Message)
            .filter(Message.interview_id == interview_id)
            .order_by(Message.created_at)
            .all()
        )

        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

    def _should_complete_interview(self, last_response: str, message_count: int) -> bool:
        """Determine if interview should complete.

        Interviews naturally complete after 8-10 exchanges or when AI
        signals completion in its response.
        """
        # Check for completion signals in AI response
        completion_phrases = [
            "thank you for your time",
            "that concludes our interview",
            "best of luck",
            "we'll be in touch",
            "appreciate you speaking with",
        ]

        response_lower = last_response.lower()
        for phrase in completion_phrases:
            if phrase in response_lower:
                return True

        # Auto-complete after ~20 messages (10 exchanges)
        if message_count >= 20:
            return True

        return False
