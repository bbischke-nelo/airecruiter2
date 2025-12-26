"""Update Workday stage processor for syncing candidate status to Workday."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.services.tms_service import TMSService

logger = structlog.get_logger()


class UpdateWorkdayStageProcessor(BaseProcessor):
    """Syncs candidate stage/disposition to Workday via Move_Candidate.

    This processor handles the async synchronization of internal application
    status changes to the external Workday system. It's queued after
    advance/reject actions to keep the UI responsive.

    Payload should contain:
    - stage_id: Target Recruiting_Stage_ID (for advancing)
    - disposition_id: Target Disposition_ID (for rejecting)
    - action: "advance" or "reject" (for logging)
    """

    job_type = "update_workday_stage"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.tms_service = TMSService(db)

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Sync application status to Workday.

        Args:
            application_id: Application to sync
            requisition_id: Not used
            payload: Must contain stage_id OR disposition_id
        """
        if not application_id:
            raise ValueError("application_id is required for update_workday_stage")

        if not payload:
            raise ValueError("payload is required for update_workday_stage")

        stage_id = payload.get("stage_id")
        disposition_id = payload.get("disposition_id")
        action = payload.get("action", "unknown")

        if not stage_id and not disposition_id:
            raise ValueError("Either stage_id or disposition_id must be in payload")

        self.logger.info(
            "Starting Workday stage sync",
            application_id=application_id,
            stage_id=stage_id,
            disposition_id=disposition_id,
            action=action,
        )

        # Get application details
        app = await self._get_application(application_id)
        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Mark as pending sync
        await self._update_sync_status(application_id, "pending", None)

        try:
            # Get Workday provider
            provider = await self.tms_service.get_provider()

            # Call Move_Candidate
            await provider.move_candidate(
                application_external_id=app.external_application_id,
                stage_id=stage_id,
                disposition_id=disposition_id,
            )

            # Mark as synced
            await self._update_sync_status(application_id, "synced", None)

            self.logger.info(
                "Workday stage sync completed",
                application_id=application_id,
                stage_id=stage_id,
                disposition_id=disposition_id,
            )

            # Log activity
            await asyncio.to_thread(
                self.log_activity,
                action="workday_stage_synced",
                application_id=application_id,
                requisition_id=app.requisition_id,
                details={
                    "stage_id": stage_id,
                    "disposition_id": disposition_id,
                    "action": action,
                },
            )

        except Exception as e:
            # Mark as failed
            error_msg = str(e)[:500]  # Truncate for DB column
            await self._update_sync_status(application_id, "failed", error_msg)

            self.logger.error(
                "Workday stage sync failed",
                application_id=application_id,
                error=str(e),
            )

            # Log activity
            await asyncio.to_thread(
                self.log_activity,
                action="workday_stage_sync_failed",
                application_id=application_id,
                requisition_id=app.requisition_id,
                details={
                    "stage_id": stage_id,
                    "disposition_id": disposition_id,
                    "action": action,
                    "error": error_msg,
                },
            )

            # Re-raise to trigger retry mechanism
            raise

    async def _get_application(self, application_id: int):
        """Fetch application from database."""
        query = text("""
            SELECT id, external_application_id, requisition_id
            FROM applications
            WHERE id = :id
        """)
        result = self.db.execute(query, {"id": application_id})
        row = result.fetchone()
        if row:
            return type("App", (), {
                "id": row[0],
                "external_application_id": row[1],
                "requisition_id": row[2],
            })()
        return None

    async def _update_sync_status(
        self,
        application_id: int,
        status: str,
        error: Optional[str],
    ) -> None:
        """Update the TMS sync status on the application."""
        if error:
            query = text("""
                UPDATE applications
                SET tms_sync_status = :status,
                    tms_sync_error = :error,
                    tms_sync_at = GETUTCDATE()
                WHERE id = :id
            """)
            self.db.execute(query, {"id": application_id, "status": status, "error": error})
        else:
            query = text("""
                UPDATE applications
                SET tms_sync_status = :status,
                    tms_sync_error = NULL,
                    tms_sync_at = GETUTCDATE()
                WHERE id = :id
            """)
            self.db.execute(query, {"id": application_id, "status": status})

        self.db.commit()
