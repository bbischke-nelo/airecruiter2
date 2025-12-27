"""Sync processor for Workday requisition and application sync."""

import json
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.services.tms_service import TMSService
from processor.tms.base import TMSApplication

logger = structlog.get_logger()


class ConcurrentUpdateError(Exception):
    """Raised when optimistic locking fails after max retries."""
    pass


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
            SELECT id, external_id, name, last_synced_at,
                   auto_send_interview, auto_send_on_status, external_data
            FROM requisitions
            WHERE id = :req_id
        """)
        result = self.db.execute(query, {"req_id": requisition_id})
        req = result.fetchone()

        if not req:
            self.logger.error("Requisition not found", requisition_id=requisition_id)
            return

        # NOTE: We intentionally do NOT use last_synced_at as a filter here.
        # The Workday API's Applied_From filter only catches NEW applications,
        # not applications whose STATUS has changed. To detect status changes
        # (e.g., moved from Screen to Interview in Workday), we must fetch ALL
        # applications each sync and compare. The APPLICATION_MIN_DATE setting
        # in provider.py limits how far back we look.

        # Extract WID from external_data if available
        wid = None
        if req.external_data:
            external_data = json.loads(req.external_data) if isinstance(req.external_data, str) else req.external_data
            wid = external_data.get("wid")

        # Fetch ALL applications from Workday to detect status changes
        applications = await provider.get_applications(req.external_id, since=None, wid=wid)

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
                    external_data = :external_data,
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
                    "external_data": json.dumps(tms_req.external_data) if tms_req.external_data else None,
                },
            )
            self.db.commit()
            return existing.id
        else:
            # Insert new
            insert_query = text("""
                INSERT INTO requisitions (external_id, name, description, detailed_description,
                                         location, is_active, sync_enabled, sync_interval_minutes,
                                         auto_send_interview, external_data, created_at)
                OUTPUT INSERTED.id
                VALUES (:external_id, :name, :description, :detailed_description,
                        :location, :is_active, 1, 15, 0, :external_data, GETUTCDATE())
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
                    "external_data": json.dumps(tms_req.external_data) if tms_req.external_data else None,
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
        # Create/update CandidateProfile first
        profile_id = await self._upsert_candidate_profile(tms_app)

        # Parse applied_at if it's a string
        applied_at = None
        if tms_app.applied_at:
            if hasattr(tms_app.applied_at, "isoformat"):
                applied_at = tms_app.applied_at
            else:
                try:
                    from datetime import datetime
                    applied_at = datetime.fromisoformat(str(tms_app.applied_at).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # Insert application with new metadata fields
        insert_query = text("""
            INSERT INTO applications (requisition_id, external_application_id, external_candidate_id,
                                     candidate_name, candidate_email, phone_number, workday_status,
                                     application_source, applied_at, candidate_profile_id,
                                     status, external_data, created_at)
            OUTPUT INSERTED.id
            VALUES (:req_id, :ext_app_id, :ext_cand_id, :name, :email, :phone, :wd_status,
                    :source, :applied_at, :profile_id, 'new', :external_data, GETUTCDATE())
        """)
        result = self.db.execute(
            insert_query,
            {
                "req_id": req.id,
                "ext_app_id": tms_app.external_application_id,
                "ext_cand_id": tms_app.external_candidate_id,
                "name": tms_app.candidate_name,
                "email": tms_app.candidate_email,
                "phone": tms_app.phone_number,
                "wd_status": tms_app.workday_status,
                "source": tms_app.application_source,
                "applied_at": applied_at,
                "profile_id": profile_id,
                "external_data": json.dumps(tms_app.external_data) if tms_app.external_data else None,
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

        # Queue resume download job (starts Human-in-the-Loop pipeline)
        self.enqueue_next(
            job_type="download_resume",
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

    async def _upsert_candidate_profile(self, tms_app: TMSApplication, max_retries: int = 3) -> Optional[int]:
        """Create or update a CandidateProfile from TMS data.

        Uses optimistic locking to prevent race conditions when multiple
        sync jobs update the same candidate profile concurrently.

        Returns:
            Profile ID or None if no external_candidate_id
        """
        if not tms_app.external_candidate_id:
            return None

        # Serialize lists to JSON
        work_history_json = json.dumps(tms_app.work_history) if tms_app.work_history else None
        education_json = json.dumps(tms_app.education) if tms_app.education else None
        skills_json = json.dumps(tms_app.skills) if tms_app.skills else None

        for attempt in range(max_retries):
            # Check if profile exists with current version
            query = text("""
                SELECT id, version FROM candidate_profiles
                WHERE external_candidate_id = :ext_cand_id
            """)
            result = self.db.execute(query, {"ext_cand_id": tms_app.external_candidate_id})
            existing = result.fetchone()

            if existing:
                # Update existing profile with optimistic lock check
                update_query = text("""
                    UPDATE candidate_profiles
                    SET candidate_wid = COALESCE(:wid, candidate_wid),
                        primary_email = COALESCE(:email, primary_email),
                        secondary_email = COALESCE(:secondary_email, secondary_email),
                        phone_number = COALESCE(:phone, phone_number),
                        city = COALESCE(:city, city),
                        state = COALESCE(:state, state),
                        work_history = COALESCE(:work_history, work_history),
                        education = COALESCE(:education, education),
                        skills = COALESCE(:skills, skills),
                        version = version + 1,
                        last_synced_at = GETUTCDATE(),
                        updated_at = GETUTCDATE()
                    WHERE id = :profile_id AND version = :expected_version
                """)
                update_result = self.db.execute(
                    update_query,
                    {
                        "profile_id": existing.id,
                        "expected_version": existing.version,
                        "wid": tms_app.candidate_wid,
                        "email": tms_app.candidate_email,
                        "secondary_email": tms_app.secondary_email,
                        "phone": tms_app.phone_number,
                        "city": tms_app.city,
                        "state": tms_app.state,
                        "work_history": work_history_json,
                        "education": education_json,
                        "skills": skills_json,
                    },
                )

                if update_result.rowcount == 0:
                    # Conflict - another process updated the profile
                    self.db.rollback()
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "Profile update conflict, retrying",
                            profile_id=existing.id,
                            attempt=attempt + 1,
                        )
                        continue
                    else:
                        # Raise exception so job can be retried later
                        raise ConcurrentUpdateError(
                            f"Failed to update profile {existing.id} after {max_retries} attempts"
                        )

                self.db.commit()
                return existing.id
            else:
                # Profile doesn't exist - try to insert
                try:
                    insert_query = text("""
                        INSERT INTO candidate_profiles (
                            external_candidate_id, candidate_wid, primary_email, secondary_email,
                            phone_number, city, state, work_history, education, skills,
                            version, last_synced_at, created_at
                        )
                        OUTPUT INSERTED.id
                        VALUES (
                            :ext_cand_id, :wid, :email, :secondary_email,
                            :phone, :city, :state, :work_history, :education, :skills,
                            0, GETUTCDATE(), GETUTCDATE()
                        )
                    """)
                    result = self.db.execute(
                        insert_query,
                        {
                            "ext_cand_id": tms_app.external_candidate_id,
                            "wid": tms_app.candidate_wid,
                            "email": tms_app.candidate_email,
                            "secondary_email": tms_app.secondary_email,
                            "phone": tms_app.phone_number,
                            "city": tms_app.city,
                            "state": tms_app.state,
                            "work_history": work_history_json,
                            "education": education_json,
                            "skills": skills_json,
                        },
                    )
                    profile_id = result.scalar()
                    self.db.commit()

                    self.logger.info(
                        "Created candidate profile",
                        profile_id=profile_id,
                        external_candidate_id=tms_app.external_candidate_id,
                    )
                    return profile_id
                except IntegrityError:
                    # Race condition - another process created the profile
                    # Retry loop will now find and update it
                    self.db.rollback()
                    self.logger.warning(
                        "Profile insert conflict, retrying as update",
                        external_candidate_id=tms_app.external_candidate_id,
                        attempt=attempt + 1,
                    )
                    continue

        # Should not reach here, but just in case
        raise ConcurrentUpdateError(
            f"Failed to upsert profile for {tms_app.external_candidate_id} after {max_retries} attempts"
        )
