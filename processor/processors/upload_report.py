"""Upload report processor for Workday attachment upload."""

from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.s3 import S3Service
from processor.services.tms_service import TMSService

logger = structlog.get_logger()


class UploadReportProcessor(BaseProcessor):
    """Uploads reports to Workday as candidate attachments."""

    job_type = "upload_report"

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
        """Process a report upload job.

        Args:
            application_id: Application whose report to upload
            requisition_id: Not used
            payload: May contain report_id
        """
        if not application_id:
            raise ValueError("application_id is required for upload_report")

        self.logger.info("Uploading report to Workday", application_id=application_id)

        try:
            # Get application and report data
            query = text("""
                SELECT a.id, a.external_candidate_id, a.candidate_name, a.requisition_id,
                       rep.id as report_id, rep.s3_key
                FROM applications a
                JOIN reports rep ON rep.application_id = a.id
                WHERE a.id = :app_id
                ORDER BY rep.created_at DESC
            """)
            result = self.db.execute(query, {"app_id": application_id})
            data = result.fetchone()

            if not data:
                raise ValueError(f"Application or report not found for {application_id}")

            if not data.external_candidate_id:
                self.logger.warning(
                    "No external candidate ID",
                    application_id=application_id,
                )
                # Mark as complete anyway
                await self._mark_complete(application_id, data.report_id, skip_upload=True)
                return

            # Download report from S3
            pdf_content = await self.s3.download(data.s3_key)

            # TEMPORARY WORKAROUND: Skip Workday upload while Put_Candidate_Attachment is broken
            # Remove this block once Workday support resolves auth issue
            # ---
            self.logger.warning(
                "Skipping Workday upload (API broken), marking as uploaded locally only",
                application_id=application_id,
            )
            doc_id = None  # No Workday document ID

            # Update report record (mark as uploaded but no Workday doc ID)
            update_query = text("""
                UPDATE reports
                SET uploaded_to_workday = 0,
                    uploaded_at = GETUTCDATE()
                WHERE id = :report_id
            """)
            self.db.execute(update_query, {"report_id": data.report_id})
            self.db.commit()
            # ---
            # END TEMPORARY WORKAROUND

            # COMMENTED OUT: Actual Workday upload - restore when API is fixed
            # # Get TMS provider
            # provider = await self.tms_service.get_provider()
            #
            # # Upload to Workday
            # filename = f"CandidateReport_{application_id}.pdf"
            # doc_id = await provider.upload_attachment(
            #     candidate_external_id=data.external_candidate_id,
            #     filename=filename,
            #     content=pdf_content,
            #     content_type="application/pdf",
            #     category="Other",  # Or use a custom category if configured
            #     comment="AI-generated candidate screening report",
            # )
            #
            # # Update report record
            # update_query = text("""
            #     UPDATE reports
            #     SET uploaded_to_workday = 1,
            #         workday_document_id = :doc_id,
            #         uploaded_at = GETUTCDATE()
            #     WHERE id = :report_id
            # """)
            # self.db.execute(
            #     update_query,
            #     {"report_id": data.report_id, "doc_id": doc_id},
            # )
            # self.db.commit()

            # Mark application as complete
            await self._mark_complete(application_id, data.report_id)

            # Log activity
            self.log_activity(
                action="report_upload_skipped",  # Changed from report_uploaded
                application_id=application_id,
                requisition_id=data.requisition_id,
                details={
                    "report_id": data.report_id,
                    "workday_upload_skipped": True,  # Workaround flag
                },
            )

            self.logger.info(
                "Report processing complete (Workday upload skipped)",
                application_id=application_id,
            )

        finally:
            await self.tms_service.close()

    async def _mark_complete(
        self,
        application_id: int,
        report_id: int,
        skip_upload: bool = False,
    ) -> None:
        """Mark application as complete."""
        update_query = text("""
            UPDATE applications
            SET status = 'complete', updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": application_id})
        self.db.commit()

        if skip_upload:
            self.logger.info(
                "Application marked complete (upload skipped)",
                application_id=application_id,
            )
        else:
            self.logger.info(
                "Application marked complete",
                application_id=application_id,
            )
