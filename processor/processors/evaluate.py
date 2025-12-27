"""Evaluate processor for interview evaluation."""

import json
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.claude import ClaudeClient

logger = structlog.get_logger()

# Path to default prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "api" / "config" / "prompts"


class EvaluateProcessor(BaseProcessor):
    """Evaluates completed interviews using Claude AI."""

    job_type = "evaluate"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.claude = ClaudeClient()

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Process an evaluation job.

        Args:
            application_id: Application to evaluate
            requisition_id: Not used
            payload: Must contain interview_id
        """
        interview_id = (payload or {}).get("interview_id")
        if not interview_id and not application_id:
            raise ValueError("interview_id or application_id is required")

        # Get interview ID from application if not provided
        if not interview_id:
            result = self.db.execute(
                text("SELECT id FROM interviews WHERE application_id = :app_id"),
                {"app_id": application_id},
            )
            row = result.fetchone()
            result.close()  # Close cursor to free connection for next query
            if not row:
                raise ValueError(f"No interview found for application {application_id}")
            interview_id = row.id

        self.logger.info("Starting interview evaluation", interview_id=interview_id)

        # Get interview with messages and candidate context
        query = text("""
            SELECT i.id, i.application_id, i.status, a.candidate_name,
                   a.requisition_id, r.name as position,
                   r.detailed_description as job_description
            FROM interviews i
            JOIN applications a ON i.application_id = a.id
            JOIN requisitions r ON a.requisition_id = r.id
            WHERE i.id = :int_id
        """)
        result = self.db.execute(query, {"int_id": interview_id})
        interview = result.fetchone()
        result.close()  # Close cursor to free connection

        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        if interview.status != "completed":
            self.logger.warning(
                "Interview not completed",
                interview_id=interview_id,
                status=interview.status,
            )
            return

        # Get messages
        messages_query = text("""
            SELECT role, content, created_at
            FROM messages
            WHERE interview_id = :int_id
            ORDER BY created_at
        """)
        messages = self.db.execute(messages_query, {"int_id": interview_id}).fetchall()

        if not messages:
            self.logger.warning("No messages in interview", interview_id=interview_id)
            return

        # Get extracted facts from analysis (resume already parsed once)
        analysis_query = text("""
            SELECT extracted_facts, relevance_summary, pros, cons
            FROM analyses
            WHERE application_id = :app_id
        """)
        analysis_result = self.db.execute(analysis_query, {"app_id": interview.application_id})
        analysis = analysis_result.fetchone()
        analysis_result.close()

        # Validate messages have content
        valid_messages = [m for m in messages if m.content and m.content.strip()]
        if len(valid_messages) < 2:  # Need at least one Q&A exchange
            self.logger.warning(
                "Insufficient interview content",
                interview_id=interview_id,
                total_messages=len(messages),
                valid_messages=len(valid_messages),
            )
            # Create minimal evaluation noting insufficient content
            await self._store_minimal_evaluation(interview_id, "Insufficient interview content for evaluation")
            return

        # Format transcript
        transcript = self._format_transcript(valid_messages, interview.candidate_name)

        # Build candidate context from extracted facts (don't re-parse resume)
        candidate_context = self._build_candidate_context(
            analysis=analysis,
            candidate_name=interview.candidate_name,
            position=interview.position,
            job_description=interview.job_description,
        )

        # Get evaluation prompt
        prompt_template = await self._get_prompt("evaluation", interview.requisition_id)

        # Call Claude for evaluation with full context
        evaluation = await self.claude.evaluate_interview(
            transcript=transcript,
            prompt_template=prompt_template,
            candidate_context=candidate_context,
        )

        # Calculate overall score (scale to 0-100 from 1-5 averages per v1)
        average_score = (
            evaluation.reliability_score +
            evaluation.accountability_score +
            evaluation.professionalism_score +
            evaluation.communication_score +
            evaluation.technical_score +
            evaluation.growth_potential_score
        ) / 6
        # Convert 1-5 scale to 0-100 scale
        overall_score = round((average_score / 5) * 100, 1)

        # Store evaluation
        await self._store_evaluation(interview_id, evaluation, overall_score, transcript)

        # Update application status
        update_query = text("""
            UPDATE applications
            SET status = 'interview_complete', updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": interview.application_id})
        self.db.commit()

        # Queue report generation
        self.enqueue_next(
            job_type="generate_report",
            application_id=interview.application_id,
            priority=0,
        )

        # Log activity
        self.log_activity(
            action="evaluation_completed",
            application_id=interview.application_id,
            requisition_id=interview.requisition_id,
            details={
                "interview_id": interview_id,
                "overall_score": overall_score,
                "recommendation": evaluation.recommendation,
            },
        )

        self.logger.info(
            "Interview evaluation complete",
            interview_id=interview_id,
            overall_score=overall_score,
            recommendation=evaluation.recommendation,
        )

    def _format_transcript(self, messages, candidate_name: str) -> str:
        """Format messages into a readable transcript."""
        lines = []
        for msg in messages:
            speaker = candidate_name if msg.role == "user" else "Interviewer"
            timestamp = msg.created_at.strftime("%H:%M:%S") if msg.created_at else ""
            lines.append(f"[{timestamp}] {speaker}: {msg.content}")
        return "\n\n".join(lines)

    def _build_candidate_context(
        self,
        analysis,
        candidate_name: str,
        position: str,
        job_description: str,
    ) -> str:
        """Build candidate context from extracted facts (resume already parsed once).

        This uses the structured data from fact extraction rather than
        re-processing the raw resume, which is more efficient.
        """
        sections = []

        sections.append(f"## Candidate: {candidate_name}")
        sections.append(f"## Position: {position}")

        if job_description:
            # Truncate job description to avoid token bloat
            jd_preview = job_description[:1500] + "..." if len(job_description) > 1500 else job_description
            sections.append(f"\n## Job Description (Summary)\n{jd_preview}")

        if analysis:
            # Use relevance summary if available
            if analysis.relevance_summary:
                sections.append(f"\n## Resume Summary\n{analysis.relevance_summary}")

            # Parse extracted facts
            extracted_facts = {}
            if analysis.extracted_facts:
                try:
                    extracted_facts = json.loads(analysis.extracted_facts) if isinstance(
                        analysis.extracted_facts, str
                    ) else analysis.extracted_facts
                except json.JSONDecodeError:
                    pass

            # Employment history (key for context)
            employment = extracted_facts.get("employment_history", [])
            if employment:
                sections.append("\n## Recent Employment")
                for job in employment[:4]:
                    title = job.get("title", "Unknown")
                    employer = job.get("employer", "Unknown")
                    duration = job.get("duration_months", 0)
                    sections.append(f"- {title} at {employer} ({duration} months)")

            # Skills
            skills = extracted_facts.get("skills", {})
            if skills:
                all_skills = []
                if isinstance(skills, dict):
                    for category_skills in skills.values():
                        if isinstance(category_skills, list):
                            all_skills.extend(category_skills[:5])
                elif isinstance(skills, list):
                    all_skills = skills[:15]
                if all_skills:
                    sections.append(f"\n## Skills\n{', '.join(all_skills[:15])}")

            # Strengths and gaps from analysis (already identified)
            if analysis.pros:
                try:
                    pros = json.loads(analysis.pros) if isinstance(analysis.pros, str) else analysis.pros
                    if pros:
                        sections.append("\n## Known Strengths")
                        for p in pros[:3]:
                            sections.append(f"- {p}")
                except json.JSONDecodeError:
                    pass

            if analysis.cons:
                try:
                    cons = json.loads(analysis.cons) if isinstance(analysis.cons, str) else analysis.cons
                    if cons:
                        sections.append("\n## Gaps/Areas to Probe")
                        for c in cons[:3]:
                            sections.append(f"- {c}")
                except json.JSONDecodeError:
                    pass
        else:
            sections.append("\n## Note: No resume data available - evaluate based on interview only")

        return "\n".join(sections)

    async def _store_minimal_evaluation(self, interview_id: int, reason: str) -> None:
        """Store a minimal evaluation when content is insufficient."""
        query = text("""
            INSERT INTO evaluations (interview_id, reliability_score, accountability_score,
                                    professionalism_score, communication_score,
                                    technical_score, growth_potential_score, overall_score,
                                    summary, strengths, weaknesses, red_flags,
                                    recommendation, created_at)
            VALUES (:int_id, 3, 3, 3, 3, 3, 3, 50,
                    :summary, '[]', '[]', '[]',
                    'review', GETUTCDATE())
        """)
        self.db.execute(
            query,
            {
                "int_id": interview_id,
                "summary": f"**Evaluation Limited:** {reason}. Unable to provide full assessment due to insufficient interview content. Recommend manual review of available materials.",
            },
        )
        self.db.commit()
        self.logger.info("Stored minimal evaluation", interview_id=interview_id, reason=reason)

    async def _get_prompt(self, prompt_type: str, requisition_id: int) -> str:
        """Get the active prompt template for a type.

        Tries database first, then file system fallback.
        """
        # Try database first
        query = text("""
            SELECT template_content
            FROM prompts
            WHERE prompt_type = :prompt_type
              AND (requisition_id = :req_id OR requisition_id IS NULL)
              AND is_active = 1
            ORDER BY requisition_id DESC
        """)
        result = self.db.execute(query, {"prompt_type": prompt_type, "req_id": requisition_id})
        row = result.fetchone()
        result.close()  # Close cursor to free connection

        if row and row.template_content:
            return row.template_content

        # Try file system fallback
        prompt_file = PROMPTS_DIR / f"{prompt_type}.md"
        if prompt_file.exists():
            self.logger.info("Loading prompt from file", prompt_type=prompt_type, path=str(prompt_file))
            return prompt_file.read_text()

        # Ultimate fallback - basic prompt
        self.logger.warning("Using basic fallback prompt", prompt_type=prompt_type)
        return """Evaluate the following interview transcript.

Transcript:
{transcript}

Provide your evaluation as JSON with the following structure:
{{
    "reliability_score": <1-10>,
    "accountability_score": <1-10>,
    "professionalism_score": <1-10>,
    "communication_score": <1-10>,
    "technical_score": <1-10>,
    "growth_potential_score": <1-10>,
    "summary": "<2-3 sentence overall assessment>",
    "strengths": ["<strength 1>", "<strength 2>", ...],
    "weaknesses": ["<weakness 1>", "<weakness 2>", ...],
    "red_flags": ["<concern 1>", "<concern 2>", ...],
    "recommendation": "<recommend|consider|do_not_recommend>"
}}
"""

    async def _store_evaluation(
        self,
        interview_id: int,
        evaluation,
        overall_score: float,
        transcript: str,
    ) -> None:
        """Store evaluation results in database."""
        query = text("""
            INSERT INTO evaluations (interview_id, reliability_score, accountability_score,
                                    professionalism_score, communication_score,
                                    technical_score, growth_potential_score, overall_score,
                                    summary, strengths, weaknesses, red_flags,
                                    character_passed, retention_risk, authenticity_assessment,
                                    readiness, next_interview_focus,
                                    recommendation, transcript, raw_response, created_at)
            VALUES (:int_id, :reliability, :accountability, :professionalism,
                    :communication, :technical, :growth, :overall,
                    :summary, :strengths, :weaknesses, :red_flags,
                    :character_passed, :retention_risk, :authenticity,
                    :readiness, :next_focus,
                    :recommendation, :transcript, :raw, GETUTCDATE())
        """)
        self.db.execute(
            query,
            {
                "int_id": interview_id,
                "reliability": evaluation.reliability_score,
                "accountability": evaluation.accountability_score,
                "professionalism": evaluation.professionalism_score,
                "communication": evaluation.communication_score,
                "technical": evaluation.technical_score,
                "growth": evaluation.growth_potential_score,
                "overall": overall_score,
                "summary": evaluation.summary,
                "strengths": json.dumps(evaluation.strengths),
                "weaknesses": json.dumps(evaluation.weaknesses),
                "red_flags": json.dumps(evaluation.red_flags),
                "character_passed": evaluation.character_passed,
                "retention_risk": evaluation.retention_risk,
                "authenticity": evaluation.authenticity_assessment,
                "readiness": evaluation.readiness,
                "next_focus": json.dumps(evaluation.next_interview_focus),
                "recommendation": evaluation.recommendation,
                "transcript": transcript,
                "raw": evaluation.raw_response,
            },
        )
        self.db.commit()
