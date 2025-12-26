"""Download resume processor for fetching resumes from Workday."""

import asyncio
import json
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.s3 import S3Service
from processor.services.tms_service import TMSService

logger = structlog.get_logger()


class DownloadResumeProcessor(BaseProcessor):
    """Downloads resumes from Workday and stores them in S3.

    Part of the Human-in-the-Loop pipeline:
    sync → download_resume → extract_facts → generate_summary → ready_for_review
    """

    job_type = "download_resume"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.s3 = S3Service()
        self.tms_service = TMSService(db)

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Download resume from Workday and store in S3.

        Args:
            application_id: Application to download resume for
            requisition_id: Not used
            payload: Additional options
        """
        if not application_id:
            raise ValueError("application_id is required for download_resume")

        self.logger.info("Starting resume download", application_id=application_id)

        # Update status to downloading
        await self._update_status(application_id, "downloading")

        # Get application details
        app = await self._get_application(application_id)
        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Get Workday provider
        try:
            provider = await self.tms_service.get_provider()

            # Download resume from Workday
            resume_data = await provider.get_resume(app.external_candidate_id)

            if resume_data:
                content, filename, content_type = resume_data

                # Upload to S3
                s3_key = await self.s3.upload_resume(application_id, content, filename)

                # Update artifacts with S3 key
                artifacts = json.loads(app.artifacts) if app.artifacts else {}
                artifacts["resume"] = s3_key
                artifacts["resume_filename"] = filename
                artifacts["resume_content_type"] = content_type
                artifacts["resume_size"] = len(content)

                await self._update_artifacts(application_id, artifacts)

                # ATOMIC: Set status + queue next job
                await self._update_status_and_queue(
                    application_id=application_id,
                    status="downloaded",
                    next_job_type="extract_facts",
                )

                self.logger.info(
                    "Resume downloaded and stored",
                    application_id=application_id,
                    s3_key=s3_key,
                    filename=filename,
                )

                # Log activity
                await asyncio.to_thread(
                    self.log_activity,
                    action="resume_downloaded",
                    application_id=application_id,
                    requisition_id=app.requisition_id,
                    details={
                        "filename": filename,
                        "size": len(content),
                        "s3_key": s3_key,
                    },
                )
            else:
                # No resume available - still proceed to extract_facts
                # (may be able to extract info from application data)
                self.logger.warning("No resume found in Workday", application_id=application_id)

                await self._update_status_and_queue(
                    application_id=application_id,
                    status="no_resume",
                    next_job_type="extract_facts",
                )

                await asyncio.to_thread(
                    self.log_activity,
                    action="no_resume_found",
                    application_id=application_id,
                    requisition_id=app.requisition_id,
                    details={"external_candidate_id": app.external_candidate_id},
                )

        finally:
            await self.tms_service.close()

    async def _get_application(self, application_id: int):
        """Get application details (async-safe)."""
        def _query():
            query = text("""
                SELECT a.id, a.external_candidate_id, a.artifacts, a.requisition_id
                FROM applications a
                WHERE a.id = :app_id
            """)
            result = self.db.execute(query, {"app_id": application_id})
            return result.fetchone()

        return await asyncio.to_thread(_query)

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

    async def _update_artifacts(self, application_id: int, artifacts: dict) -> None:
        """Update application artifacts (async-safe)."""
        def _update():
            query = text("""
                UPDATE applications
                SET artifacts = :artifacts, updated_at = GETUTCDATE()
                WHERE id = :app_id
            """)
            self.db.execute(query, {"app_id": application_id, "artifacts": json.dumps(artifacts)})
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
