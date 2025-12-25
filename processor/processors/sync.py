"""Sync processor for Workday requisition and application sync."""

import json
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.services.tms_service import TMSService
from processor.tms.base import TMSApplication

logger = structlog.get_logger()


class SyncProcessor(BaseProcessor):
    """Syncs requisitions and applications from Workday."""

    job_type = "sync"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.tms_service = TMSService(db)

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Process a sync job.

        If requisition_id is provided, sync that requisition.
        Otherwise, perform a full sync of all active requisitions.

        Args:
            application_id: Not used for sync jobs
            requisition_id: Optional specific requisition to sync
            payload: Additional options (e.g., full_sync: bool)
        """
        try:
            provider = await self.tms_service.get_provider()

            if requisition_id:
                await self._sync_requisition(provider, requisition_id)
            else:
                await self._sync_all_requisitions(provider)

        finally:
            await self.tms_service.close()

    async def _sync_all_requisitions(self, provider) -> None:
        """Sync all active requisitions from Workday."""
        self.logger.info("Starting full sync")

        # Fetch all open requisitions from Workday
        tms_requisitions = await provider.get_requisitions(active_only=True)

        for tms_req in tms_requisitions:
            await self._upsert_requisition(tms_req)

        self.log_activity(
            action="sync_completed",
            details={"requisition_count": len(tms_requisitions)},
        )

        self.logger.info("Full sync completed", requisition_count=len(tms_requisitions))

    async def _sync_requisition(self, provider, requisition_id: int) -> None:
        """Sync a single requisition and its applications."""
        self.logger.info("Syncing requisition", requisition_id=requisition_id)

        # Get requisition from database
        query = text("""
            SELECT id, external_id, name, last_synced_at, lookback_hours,
                   auto_send_interview, auto_send_on_status
            FROM requisitions
            WHERE id = :req_id
        """)
        result = self.db.execute(query, {"req_id": requisition_id})
        req = result.fetchone()

        if not req:
            self.logger.error("Requisition not found", requisition_id=requisition_id)
            return

        # Calculate since date for incremental sync
        since = None
        if req.last_synced_at:
            since = req.last_synced_at

        # Fetch applications from Workday
        applications = await provider.get_applications(req.external_id, since=since)

        new_count = 0
        updated_count = 0

        for tms_app in applications:
            is_new = await self._process_application(req, tms_app, provider)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        # Update last_synced_at
        update_query = text("""
            UPDATE requisitions
            SET last_synced_at = GETUTCDATE()
            WHERE id = :req_id
        """)
        self.db.execute(update_query, {"req_id": requisition_id})
        self.db.commit()

        self.log_activity(
            action="requisition_synced",
            requisition_id=requisition_id,
            details={
                "external_id": req.external_id,
                "new_applications": new_count,
                "updated_applications": updated_count,
            },
        )

        self.logger.info(
            "Requisition sync completed",
            requisition_id=requisition_id,
            new_applications=new_count,
            updated_applications=updated_count,
        )

    async def _upsert_requisition(self, tms_req) -> int:
        """Insert or update a requisition from TMS data.

        Returns:
            Requisition ID
        """
        # Check if requisition exists
        query = text("SELECT id FROM requisitions WHERE external_id = :ext_id")
        result = self.db.execute(query, {"ext_id": tms_req.external_id})
        existing = result.fetchone()

        if existing:
            # Update existing
            update_query = text("""
                UPDATE requisitions
                SET name = :name,
                    description = :description,
                    detailed_description = :detailed_description,
                    location = :location,
                    is_active = :is_active,
                    workday_data = :workday_data,
                    updated_at = GETUTCDATE()
                WHERE id = :req_id
            """)
            self.db.execute(
                update_query,
                {
                    "req_id": existing.id,
                    "name": tms_req.name,
                    "description": tms_req.description,
                    "detailed_description": tms_req.detailed_description,
                    "location": tms_req.location,
                    "is_active": tms_req.is_active,
                    "workday_data": json.dumps(tms_req.workday_data) if tms_req.workday_data else None,
                },
            )
            self.db.commit()
            return existing.id
        else:
            # Insert new
            insert_query = text("""
                INSERT INTO requisitions (external_id, name, description, detailed_description,
                                         location, is_active, sync_enabled, sync_interval_minutes,
                                         auto_send_interview, workday_data, created_at)
                OUTPUT INSERTED.id
                VALUES (:external_id, :name, :description, :detailed_description,
                        :location, :is_active, 1, 15, 0, :workday_data, GETUTCDATE())
            """)
            result = self.db.execute(
                insert_query,
                {
                    "external_id": tms_req.external_id,
                    "name": tms_req.name,
                    "description": tms_req.description,
                    "detailed_description": tms_req.detailed_description,
                    "location": tms_req.location,
                    "is_active": tms_req.is_active,
                    "workday_data": json.dumps(tms_req.workday_data) if tms_req.workday_data else None,
                },
            )
            # Must fetch before commit with pyodbc
            new_id = result.scalar()
            self.db.commit()
            return new_id

    async def _process_application(self, req, tms_app: TMSApplication, provider) -> bool:
        """Process a single application from TMS.

        Returns:
            True if application was new, False if existing
        """
        # Check if application exists
        query = text("""
            SELECT id, workday_status, status
            FROM applications
            WHERE external_application_id = :ext_id
        """)
        result = self.db.execute(query, {"ext_id": tms_app.external_application_id})
        existing = result.fetchone()

        if existing:
            # Update existing application
            await self._update_existing_application(req, existing, tms_app)
            return False
        else:
            # Create new application
            await self._create_new_application(req, tms_app, provider)
            return True

    async def _update_existing_application(self, req, existing, tms_app: TMSApplication) -> None:
        """Update an existing application with new TMS data."""
        # Check if Workday status changed
        if existing.workday_status != tms_app.workday_status:
            update_query = text("""
                UPDATE applications
                SET workday_status = :workday_status,
                    workday_status_changed = GETUTCDATE(),
                    updated_at = GETUTCDATE()
                WHERE id = :app_id
            """)
            self.db.execute(
                update_query,
                {
                    "app_id": existing.id,
                    "workday_status": tms_app.workday_status,
                },
            )
            self.db.commit()

            self.log_activity(
                action="workday_status_changed",
                application_id=existing.id,
                requisition_id=req.id,
                details={
                    "from": existing.workday_status,
                    "to": tms_app.workday_status,
                },
            )

            # Check if auto-send interview should trigger
            if (req.auto_send_interview and
                req.auto_send_on_status == tms_app.workday_status and
                existing.status == "analyzed"):

                self.enqueue_next(
                    job_type="send_interview",
                    application_id=existing.id,
                    priority=1,
                )
                self.logger.info(
                    "Auto-queued interview send",
                    application_id=existing.id,
                    trigger_status=tms_app.workday_status,
                )

    async def _create_new_application(self, req, tms_app: TMSApplication, provider) -> None:
        """Create a new application from TMS data."""
        # Insert application
        insert_query = text("""
            INSERT INTO applications (requisition_id, external_application_id, external_candidate_id,
                                     candidate_name, candidate_email, workday_status, status,
                                     workday_data, created_at)
            OUTPUT INSERTED.id
            VALUES (:req_id, :ext_app_id, :ext_cand_id, :name, :email, :wd_status, 'new',
                    :workday_data, GETUTCDATE())
        """)
        result = self.db.execute(
            insert_query,
            {
                "req_id": req.id,
                "ext_app_id": tms_app.external_application_id,
                "ext_cand_id": tms_app.external_candidate_id,
                "name": tms_app.candidate_name,
                "email": tms_app.candidate_email,
                "wd_status": tms_app.workday_status,
                "workday_data": json.dumps(tms_app.workday_data) if tms_app.workday_data else None,
            },
        )
        # Must fetch before commit with pyodbc
        app_id = result.scalar()
        self.db.commit()

        self.logger.info(
            "Created new application",
            application_id=app_id,
            candidate=tms_app.candidate_name,
        )

        # Download resume
        resume_data = await provider.get_resume(tms_app.external_candidate_id)
        if resume_data:
            content, filename, content_type = resume_data

            # Store resume reference (actual S3 upload will be in Phase 6)
            artifacts = {
                "resume_filename": filename,
                "resume_content_type": content_type,
                "resume_size": len(content),
            }

            update_query = text("""
                UPDATE applications
                SET artifacts = :artifacts
                WHERE id = :app_id
            """)
            self.db.execute(
                update_query,
                {
                    "app_id": app_id,
                    "artifacts": json.dumps(artifacts),
                },
            )
            self.db.commit()

            self.logger.info(
                "Resume downloaded",
                application_id=app_id,
                filename=filename,
            )

        # Queue analysis job
        self.enqueue_next(
            job_type="analyze",
            application_id=app_id,
            priority=0,
        )

        self.log_activity(
            action="application_created",
            application_id=app_id,
            requisition_id=req.id,
            details={
                "candidate_name": tms_app.candidate_name,
                "workday_status": tms_app.workday_status,
                "has_resume": resume_data is not None,
            },
        )
