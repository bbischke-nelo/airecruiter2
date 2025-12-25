"""Analyze processor for resume analysis."""

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

# Path to default prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "api" / "config" / "prompts"

# Process pool for CPU-bound text extraction
_process_pool: Optional[ProcessPoolExecutor] = None


def _get_process_pool() -> ProcessPoolExecutor:
    """Get or create the process pool for CPU-bound tasks."""
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=2)
    return _process_pool


class AnalyzeProcessor(BaseProcessor):
    """Analyzes resumes using Claude AI."""

    job_type = "analyze"

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
        """Process an analysis job.

        Args:
            application_id: Application to analyze
            requisition_id: Not used
            payload: Additional options
        """
        if not application_id:
            raise ValueError("application_id is required for analysis")

        self.logger.info("Starting resume analysis", application_id=application_id)

        # Get application with requisition (run in thread to avoid blocking)
        app = await self._get_application(application_id)

        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Parse artifacts
        artifacts = json.loads(app.artifacts) if app.artifacts else {}
        resume_key = artifacts.get("resume")

        if not resume_key:
            self.logger.warning("No resume found", application_id=application_id)
            # Mark as analyzed with note
            await self._update_status(application_id, "analyzed", "No resume available")
            return

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
            self.logger.warning("Empty resume text", application_id=application_id)
            await self._update_status(application_id, "analyzed", "Could not extract text from resume")
            return

        # Get analysis prompt
        prompt_template = await self._get_prompt("resume_analysis", app.requisition_id)

        # Call Claude for analysis
        analysis = await self.claude.analyze_resume(
            resume_text=resume_text,
            job_description=app.detailed_description or f"Position: {app.position}",
            prompt_template=prompt_template,
        )

        # Store analysis (run in thread)
        await self._store_analysis(application_id, analysis)

        # Update application status
        await self._update_status(application_id, "analyzed")

        # Log activity
        await asyncio.to_thread(
            self.log_activity,
            action="analysis_completed",
            application_id=application_id,
            requisition_id=app.requisition_id,
            details={
                "risk_score": analysis.risk_score,
                "pros_count": len(analysis.pros),
                "cons_count": len(analysis.cons),
                "red_flags_count": len(analysis.red_flags),
            },
        )

        self.logger.info(
            "Resume analysis complete",
            application_id=application_id,
            risk_score=analysis.risk_score,
        )

    async def _get_application(self, application_id: int):
        """Get application with requisition data (async-safe)."""
        def _query():
            query = text("""
                SELECT a.id, a.candidate_name, a.artifacts, a.requisition_id,
                       r.detailed_description, r.name as position
                FROM applications a
                JOIN requisitions r ON a.requisition_id = r.id
                WHERE a.id = :app_id
            """)
            result = self.db.execute(query, {"app_id": application_id})
            return result.fetchone()

        return await asyncio.to_thread(_query)

    async def _get_prompt(self, prompt_type: str, requisition_id: int) -> str:
        """Get the active prompt template for a type (async-safe).

        Tries database first, then file system fallback.
        """
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
            template = prompt_file.read_text()

            # Load example JSON if it exists (for resume_analysis)
            example_file = PROMPTS_DIR / f"{prompt_type}_example.json"
            if example_file.exists():
                example_json = example_file.read_text()
                template = template.replace("${example}", example_json)

            return template

        # Ultimate fallback - basic prompt
        self.logger.warning("Using basic fallback prompt", prompt_type=prompt_type)
        return """Analyze the following resume against the job requirements.

Job Description:
{job_description}

Resume:
{resume}

Provide your analysis as JSON with the following structure:
{{
    "risk_score": <1-10 scale, 10 = highest risk/least qualified>,
    "relevance_summary": "<2-3 sentence summary of fit>",
    "pros": ["<strength 1>", "<strength 2>", ...],
    "cons": ["<weakness 1>", "<weakness 2>", ...],
    "red_flags": ["<concern 1>", "<concern 2>", ...],
    "suggested_questions": ["<question 1>", "<question 2>", ...]
}}

Focus on:
- Relevant experience and skills match
- Employment history patterns
- Education alignment
- Any gaps or inconsistencies
"""

    async def _store_analysis(self, application_id: int, analysis) -> None:
        """Store analysis results in database (async-safe)."""
        def _insert():
            query = text("""
                INSERT INTO analyses (application_id, risk_score, relevance_summary,
                                     pros, cons, red_flags, suggested_questions,
                                     raw_response, created_at)
                VALUES (:app_id, :risk_score, :summary, :pros, :cons, :red_flags,
                        :questions, :raw, GETUTCDATE())
            """)
            self.db.execute(
                query,
                {
                    "app_id": application_id,
                    "risk_score": analysis.risk_score,
                    "summary": analysis.relevance_summary,
                    "pros": json.dumps(analysis.pros),
                    "cons": json.dumps(analysis.cons),
                    "red_flags": json.dumps(analysis.red_flags),
                    "questions": json.dumps(analysis.suggested_questions),
                    "raw": analysis.raw_response,
                },
            )
            self.db.commit()

        await asyncio.to_thread(_insert)

    async def _update_status(
        self,
        application_id: int,
        status: str,
        note: Optional[str] = None,
    ) -> None:
        """Update application status (async-safe)."""
        def _update():
            if note:
                query = text("""
                    UPDATE applications
                    SET status = :status, notes = :note, updated_at = GETUTCDATE()
                    WHERE id = :app_id
                """)
                self.db.execute(query, {"app_id": application_id, "status": status, "note": note})
            else:
                query = text("""
                    UPDATE applications
                    SET status = :status, updated_at = GETUTCDATE()
                    WHERE id = :app_id
                """)
                self.db.execute(query, {"app_id": application_id, "status": status})
            self.db.commit()

        await asyncio.to_thread(_update)
