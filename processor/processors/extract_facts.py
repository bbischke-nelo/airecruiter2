"""Extract facts processor for AI-powered resume fact extraction.

Part of the Human-in-the-Loop pipeline - extracts factual information only.
NO scoring, ranking, or recommendations. Humans make all decisions.
"""

import asyncio
import json
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.claude import ClaudeClient
from processor.integrations.s3 import S3Service
from processor.utils.pdf_extractor import extract_text_from_file

logger = structlog.get_logger()

# Path to prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "api" / "config" / "prompts"

# Process pool for CPU-bound text extraction
_process_pool: Optional[ProcessPoolExecutor] = None


def _get_process_pool() -> ProcessPoolExecutor:
    """Get or create the process pool for CPU-bound tasks."""
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=2)
    return _process_pool


class ExtractFactsProcessor(BaseProcessor):
    """Extracts factual information from resumes using Claude AI.

    Part of the Human-in-the-Loop pipeline:
    sync → download_resume → extract_facts → generate_summary → ready_for_review

    This processor:
    - Extracts employment history, skills, certifications, education
    - Matches extracted facts against JD requirements
    - Generates observations (pros/cons) tied to JD
    - Suggests clarifying questions
    - Does NOT score, rank, or recommend decisions
    """

    job_type = "extract_facts"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.claude = ClaudeClient()
        self.s3 = S3Service()

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Extract facts from resume.

        Args:
            application_id: Application to analyze
            requisition_id: Not used
            payload: Additional options
        """
        if not application_id:
            raise ValueError("application_id is required for extract_facts")

        self.logger.info("Starting fact extraction", application_id=application_id)

        # Update status to extracting
        await self._update_status(application_id, "extracting")

        # Get application with requisition data
        app = await self._get_application(application_id)
        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Parse artifacts
        artifacts = json.loads(app.artifacts) if app.artifacts else {}
        resume_key = artifacts.get("resume")

        resume_text = ""
        extraction_notes = None

        if resume_key:
            try:
                # Download resume from S3
                resume_content = await self.s3.download(resume_key)

                # Extract text in process pool (CPU-bound operation)
                filename = artifacts.get("resume_filename", "resume.pdf")
                loop = asyncio.get_event_loop()
                resume_text = await loop.run_in_executor(
                    _get_process_pool(),
                    partial(extract_text_from_file, resume_content, filename),
                )

                if not resume_text.strip():
                    extraction_notes = "Could not extract text from resume file"
                    self.logger.warning("Empty resume text", application_id=application_id)
            except Exception as e:
                extraction_notes = f"Error extracting resume: {str(e)}"
                self.logger.error("Resume extraction error", application_id=application_id, error=str(e))
        else:
            extraction_notes = "No resume available"
            self.logger.warning("No resume for extraction", application_id=application_id)

        # Get fact extraction prompt
        prompt_template = await self._get_prompt("fact_extraction", app.requisition_id)

        # Build Workday profile dict if data available (from joined candidate_profiles table)
        workday_profile = None
        # Access profile data from SQL result (cp.work_history, cp.education, cp.skills)
        work_history = getattr(app, "work_history", None)
        education = getattr(app, "education", None)
        skills = getattr(app, "skills", None)

        if work_history or education or skills:
            workday_profile = {}
            if work_history:
                try:
                    workday_profile["work_history"] = json.loads(work_history) if isinstance(work_history, str) else work_history
                except (json.JSONDecodeError, TypeError):
                    pass
            if education:
                try:
                    workday_profile["education"] = json.loads(education) if isinstance(education, str) else education
                except (json.JSONDecodeError, TypeError):
                    pass
            if skills:
                try:
                    workday_profile["skills"] = json.loads(skills) if isinstance(skills, str) else skills
                except (json.JSONDecodeError, TypeError):
                    pass

        # Use applied_at if available, fall back to created_at
        application_date = None
        if hasattr(app, "applied_at") and app.applied_at:
            application_date = str(app.applied_at)
        elif app.created_at:
            application_date = str(app.created_at)

        # Call Claude for fact extraction (even if resume text is empty/partial)
        # Claude can still extract facts from application data
        try:
            facts = await self.claude.extract_facts(
                resume_text=resume_text or "No resume text available",
                job_description=app.detailed_description or f"Position: {app.position}",
                prompt_template=prompt_template,
                candidate_id=app.external_candidate_id,
                application_date=application_date,
                # Additional context
                requisition_title=app.position,
                role_level=getattr(app, "role_level", None),
                location=getattr(app, "location", None),
                application_source=getattr(app, "application_source", None),
                workday_profile=workday_profile if workday_profile else None,
            )

            # Store extraction results
            await self._store_extraction(application_id, facts, extraction_notes)

            # ATOMIC: Set status + queue next job
            status = "extracted" if not extraction_notes else "extraction_failed"
            await self._update_status_and_queue(
                application_id=application_id,
                status=status,
                next_job_type="generate_report",  # Will be updated to generate_summary
            )

            # Log activity
            await asyncio.to_thread(
                self.log_activity,
                action="facts_extracted",
                application_id=application_id,
                requisition_id=app.requisition_id,
                details={
                    "employers_count": len(facts.employment_history) if facts.employment_history else 0,
                    "skills_count": len(facts.skills.get("technical", [])) if facts.skills else 0,
                    "certs_count": len(facts.certifications) if facts.certifications else 0,
                    "pros_count": len(facts.observations.get("pros", [])) if facts.observations else 0,
                    "cons_count": len(facts.observations.get("cons", [])) if facts.observations else 0,
                    "had_extraction_issues": extraction_notes is not None,
                },
            )

            self.logger.info(
                "Fact extraction complete",
                application_id=application_id,
                had_issues=extraction_notes is not None,
            )

        except Exception as e:
            # Extraction failed - still proceed to summary with notes
            self.logger.error("Claude extraction failed", application_id=application_id, error=str(e))
            extraction_notes = (extraction_notes or "") + f" Claude error: {str(e)}"

            await self._store_extraction_failure(application_id, extraction_notes)
            await self._update_status_and_queue(
                application_id=application_id,
                status="extraction_failed",
                next_job_type="generate_report",
            )

    async def _get_application(self, application_id: int):
        """Get application with requisition and candidate profile data (async-safe)."""
        def _query():
            query = text("""
                SELECT a.id, a.external_candidate_id, a.candidate_name, a.artifacts,
                       a.requisition_id, a.created_at, a.applied_at, a.application_source,
                       a.candidate_profile_id,
                       r.detailed_description, r.name as position, r.role_level, r.location,
                       cp.work_history, cp.education, cp.skills
                FROM applications a
                JOIN requisitions r ON a.requisition_id = r.id
                LEFT JOIN candidate_profiles cp ON a.candidate_profile_id = cp.id
                WHERE a.id = :app_id
            """)
            result = self.db.execute(query, {"app_id": application_id})
            return result.fetchone()

        return await asyncio.to_thread(_query)

    async def _get_prompt(self, prompt_type: str, requisition_id: int) -> str:
        """Get the active prompt template (async-safe)."""
        def _query():
            query = text("""
                SELECT template_content
                FROM prompts
                WHERE prompt_type = :prompt_type
                  AND (requisition_id = :req_id OR requisition_id IS NULL)
                  AND is_active = 1
                ORDER BY requisition_id DESC
            """)
            result = self.db.execute(query, {"prompt_type": prompt_type, "req_id": requisition_id})
            return result.fetchone()

        row = await asyncio.to_thread(_query)

        if row and row.template_content:
            return row.template_content

        # Try file system fallback
        prompt_file = PROMPTS_DIR / f"{prompt_type}.md"
        if prompt_file.exists():
            self.logger.info("Loading prompt from file", prompt_type=prompt_type, path=str(prompt_file))
            return prompt_file.read_text()

        # Ultimate fallback - basic fact extraction prompt
        self.logger.warning("Using basic fallback prompt", prompt_type=prompt_type)
        return self._get_fallback_prompt()

    def _get_fallback_prompt(self) -> str:
        """Get minimal fallback prompt for fact extraction."""
        return """Extract factual information from this resume. DO NOT score, rank, or make recommendations.

Job Description:
{job_description}

Resume:
{resume}

Return as JSON with this structure:
{{
    "extraction_version": "1.0",
    "employment_history": [
        {{"employer": "...", "title": "...", "start_date": "...", "end_date": "...", "duration_months": 0}}
    ],
    "skills": {{
        "technical": ["..."],
        "software": ["..."],
        "industry_specific": ["..."]
    }},
    "certifications": [
        {{"name": "...", "issuer": "...", "date_obtained": "..."}}
    ],
    "education": [
        {{"institution": "...", "degree": "...", "field": "...", "graduation_date": "..."}}
    ],
    "summary_stats": {{
        "total_experience_months": 0,
        "recent_5yr_employers_count": 0,
        "recent_5yr_average_tenure_months": 0
    }},
    "observations": {{
        "pros": [{{"category": "...", "observation": "...", "evidence": "..."}}],
        "cons": [{{"category": "...", "observation": "...", "evidence": "..."}}],
        "suggested_questions": [{{"topic": "...", "question": "...", "reason": "..."}}]
    }}
}}

Extract ONLY facts explicitly stated. Use null for anything not found.
"""

    async def _store_extraction(self, application_id: int, facts, notes: Optional[str]) -> None:
        """Store extraction results in database (async-safe)."""
        def _insert():
            # Convert facts object to JSON
            extracted_facts_json = json.dumps({
                "extraction_version": getattr(facts, "extraction_version", "1.0"),
                "employment_history": facts.employment_history if hasattr(facts, "employment_history") else [],
                "skills": facts.skills if hasattr(facts, "skills") else {},
                "certifications": facts.certifications if hasattr(facts, "certifications") else [],
                "licenses": facts.licenses if hasattr(facts, "licenses") else [],
                "education": facts.education if hasattr(facts, "education") else [],
                "summary_stats": facts.summary_stats if hasattr(facts, "summary_stats") else {},
                "jd_requirements_match": facts.jd_requirements_match if hasattr(facts, "jd_requirements_match") else {},
            })

            observations = facts.observations if hasattr(facts, "observations") else {}

            query = text("""
                INSERT INTO analyses (application_id, extracted_facts, extraction_version, extraction_notes,
                                     relevance_summary, pros, cons, suggested_questions,
                                     raw_response, created_at)
                VALUES (:app_id, :extracted_facts, :version, :notes, :summary,
                        :pros, :cons, :questions, :raw, GETUTCDATE())
            """)
            self.db.execute(
                query,
                {
                    "app_id": application_id,
                    "extracted_facts": extracted_facts_json,
                    "version": getattr(facts, "extraction_version", "1.0"),
                    "notes": notes,
                    "summary": getattr(facts, "relevance_summary", None),
                    "pros": json.dumps(observations.get("pros", [])),
                    "cons": json.dumps(observations.get("cons", [])),
                    "questions": json.dumps(observations.get("suggested_questions", [])),
                    "raw": facts.raw_response if hasattr(facts, "raw_response") else None,
                },
            )
            self.db.commit()

        await asyncio.to_thread(_insert)

    async def _store_extraction_failure(self, application_id: int, notes: str) -> None:
        """Store extraction failure in database (async-safe)."""
        def _insert():
            query = text("""
                INSERT INTO analyses (application_id, extraction_notes, created_at)
                VALUES (:app_id, :notes, GETUTCDATE())
            """)
            self.db.execute(query, {"app_id": application_id, "notes": notes})
            self.db.commit()

        await asyncio.to_thread(_insert)

    async def _update_status(self, application_id: int, status: str) -> None:
        """Update application status (async-safe)."""
        def _update():
            query = text("""
                UPDATE applications
                SET status = :status, updated_at = GETUTCDATE()
                WHERE id = :app_id
            """)
            self.db.execute(query, {"app_id": application_id, "status": status})
            self.db.commit()

        await asyncio.to_thread(_update)

    async def _update_status_and_queue(
        self,
        application_id: int,
        status: str,
        next_job_type: str,
    ) -> None:
        """ATOMIC: Update status and queue next job in same transaction."""
        def _atomic_update():
            # Update status
            update_query = text("""
                UPDATE applications
                SET status = :status, updated_at = GETUTCDATE()
                WHERE id = :app_id
            """)
            self.db.execute(update_query, {"app_id": application_id, "status": status})

            # Queue next job
            insert_query = text("""
                INSERT INTO jobs (application_id, job_type, status, priority, created_at, scheduled_for)
                VALUES (:app_id, :job_type, 'pending', 0, GETUTCDATE(), GETUTCDATE())
            """)
            self.db.execute(insert_query, {"app_id": application_id, "job_type": next_job_type})

            self.db.commit()

        await asyncio.to_thread(_atomic_update)
        self.logger.info(
            "Status updated and next job queued",
            application_id=application_id,
            status=status,
            next_job=next_job_type,
        )
