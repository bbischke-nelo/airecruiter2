"""Scheduler for periodic job creation."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.config import settings
from processor.queue_manager import QueueManager

logger = structlog.get_logger()


class Scheduler:
    """Periodically checks for work and creates queue jobs."""

    def __init__(self, db: Session):
        """Initialize scheduler.

        Args:
            db: Database session
        """
        self.db = db
        self.queue = QueueManager(db)
        self.running = False
        self.interval = settings.SCHEDULER_INTERVAL
        self.last_run: Optional[datetime] = None

    async def run(self) -> None:
        """Main scheduler loop."""
        self.running = True
        logger.info(
            "Scheduler started",
            interval=self.interval,
        )

        while self.running:
            try:
                await self.check_for_work()
                self.last_run = datetime.now(timezone.utc)
            except Exception as e:
                logger.error("Scheduler error", error=str(e), exc_info=True)

            await asyncio.sleep(self.interval)

        logger.info("Scheduler stopped")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False

    async def check_for_work(self) -> None:
        """Check for work that needs to be done."""
        logger.debug("Checking for work")

        # 0. Check if requisitions need to be synced from Workday (full refresh)
        await self._queue_requisition_sync()

        # 1. Check for active requisitions that need syncing (applicants)
        await self._queue_sync_jobs()

        # 2. Check for applications stuck in intermediate pipeline states
        # Pipeline: new → download_resume → downloaded → extract_facts → extracted → generate_report → ready_for_review
        await self._queue_stuck_jobs()

        # 3. Check for ready_for_review applications ready for interview (auto-send)
        await self._queue_interview_jobs()

        # 4. Check for completed interviews needing evaluation
        await self._queue_evaluation_jobs()

        # 5. Check for evaluated interviews needing reports
        await self._queue_report_jobs()

    async def _queue_requisition_sync(self) -> None:
        """Queue a full requisition sync if interval has elapsed.

        This syncs the list of requisitions from Workday (not applicants).
        """
        # Check last sync time from settings
        query = text("""
            SELECT value FROM settings WHERE [key] = 'last_requisition_sync'
        """)
        result = self.db.execute(query)
        row = result.fetchone()

        should_sync = False
        if not row or not row.value:
            should_sync = True
        else:
            try:
                last_sync = datetime.fromisoformat(row.value.replace("Z", "+00:00"))
                minutes_since = (datetime.now(timezone.utc) - last_sync).total_seconds() / 60
                if minutes_since >= settings.REQUISITION_SYNC_INTERVAL:
                    should_sync = True
            except (ValueError, TypeError):
                should_sync = True

        if not should_sync:
            return

        # Check if there's already a pending/running requisition sync job (no requisition_id)
        check_query = text("""
            SELECT 1 FROM jobs
            WHERE job_type = 'sync'
              AND requisition_id IS NULL
              AND status IN ('pending', 'running')
        """)
        result = self.db.execute(check_query)
        if result.fetchone():
            return  # Already have a pending requisition sync

        # Queue the sync job (no requisition_id = full requisition sync)
        self.queue.enqueue(
            job_type="sync",
            priority=0,
        )

        # Update last sync time
        upsert_query = text("""
            MERGE settings AS target
            USING (SELECT 'last_requisition_sync' as [key]) AS source
            ON target.[key] = source.[key]
            WHEN MATCHED THEN UPDATE SET value = :value
            WHEN NOT MATCHED THEN INSERT ([key], value) VALUES ('last_requisition_sync', :value);
        """)
        self.db.execute(upsert_query, {"value": datetime.now(timezone.utc).isoformat()})
        self.db.commit()

        logger.info("Queued requisition sync job", interval_minutes=settings.REQUISITION_SYNC_INTERVAL)

    async def _queue_sync_jobs(self) -> None:
        """Queue sync jobs for active requisitions (applicants)."""
        # Get active requisitions that need syncing based on their sync_interval_minutes
        query = text("""
            SELECT r.id, r.external_id, r.name
            FROM requisitions r
            WHERE r.is_active = 1
              AND r.sync_enabled = 1
              AND (
                  r.last_synced_at IS NULL
                  OR DATEDIFF(MINUTE, r.last_synced_at, GETUTCDATE()) >= r.sync_interval_minutes
              )
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.requisition_id = r.id
                    AND j.job_type = 'sync'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()  # Must fetch all before executing another query

        for row in rows:
            self.queue.enqueue(
                job_type="sync",
                requisition_id=row.id,
                priority=0,
            )
            logger.info("Queued sync job", requisition_id=row.id, requisition_name=row.name)

    async def _queue_stuck_jobs(self) -> None:
        """Queue jobs for applications that are stuck in intermediate states.

        This catches applications that missed their next job due to failures.
        The primary flow is: sync → download_resume → extract_facts → generate_report → ready_for_review
        """
        # Applications stuck in 'new' status without a pending download_resume job
        # (sync should have queued this, but may have failed)
        query = text("""
            SELECT a.id, a.candidate_name, a.status
            FROM applications a
            WHERE a.status = 'new'
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'download_resume'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()

        for row in rows:
            self.queue.enqueue(
                job_type="download_resume",
                application_id=row.id,
                priority=0,
            )
            logger.info("Queued download_resume for stuck new app", application_id=row.id, candidate=row.candidate_name)

        # Applications stuck in 'downloaded' or 'no_resume' without extract_facts job
        query = text("""
            SELECT a.id, a.candidate_name, a.status
            FROM applications a
            WHERE a.status IN ('downloaded', 'no_resume')
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'extract_facts'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()

        for row in rows:
            self.queue.enqueue(
                job_type="extract_facts",
                application_id=row.id,
                priority=0,
            )
            logger.info("Queued extract_facts for stuck app", application_id=row.id, status=row.status, candidate=row.candidate_name)

        # Applications stuck in 'extracted' or 'extraction_failed' without generate_report job
        query = text("""
            SELECT a.id, a.candidate_name, a.status
            FROM applications a
            WHERE a.status IN ('extracted', 'extraction_failed')
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'generate_report'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()

        for row in rows:
            self.queue.enqueue(
                job_type="generate_report",
                application_id=row.id,
                priority=0,
            )
            logger.info("Queued generate_report for stuck app", application_id=row.id, status=row.status, candidate=row.candidate_name)

        # Handle legacy 'analyzed' status from old pipeline - transition to new pipeline
        # These apps already have analysis, so queue generate_report to create summary and move to ready_for_review
        query = text("""
            SELECT a.id, a.candidate_name
            FROM applications a
            WHERE a.status = 'analyzed'
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'generate_report'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()

        for row in rows:
            self.queue.enqueue(
                job_type="generate_report",
                application_id=row.id,
                priority=0,
            )
            logger.info("Queued generate_report for legacy analyzed app", application_id=row.id, candidate=row.candidate_name)

    async def _queue_interview_jobs(self) -> None:
        """Queue interview send jobs for ready_for_review applications with auto-send enabled.

        Uses 3-state logic for auto_send_interview:
        - True (1): Always auto-send for this requisition
        - False (0): Never auto-send for this requisition
        - NULL: Use global default (auto_send_interview_default setting)

        Note: In HITL mode, auto-send is typically disabled (default=false).
        Humans review candidates and manually trigger interviews from the UI.
        """
        # First get the global default setting
        global_default_query = text("""
            SELECT value FROM settings WHERE [key] = 'auto_send_interview_default'
        """)
        result = self.db.execute(global_default_query)
        row = result.fetchone()
        global_default = row.value.lower() == 'true' if row else False

        # Query applications where auto-send should happen:
        # - requisition.auto_send_interview = 1, OR
        # - requisition.auto_send_interview IS NULL AND global_default = true
        query = text("""
            SELECT a.id, a.candidate_name, r.name as requisition_name
            FROM applications a
            JOIN requisitions r ON a.requisition_id = r.id
            WHERE a.status = 'ready_for_review'
              AND (
                  r.auto_send_interview = 1
                  OR (r.auto_send_interview IS NULL AND :global_default = 1)
              )
              AND (
                  r.auto_send_on_status IS NULL
                  OR a.workday_status = r.auto_send_on_status
              )
              AND NOT EXISTS (
                  SELECT 1 FROM interviews i WHERE i.application_id = a.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'send_interview'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query, {"global_default": 1 if global_default else 0})
        rows = result.fetchall()  # Must fetch all before executing another query

        for row in rows:
            self.queue.enqueue(
                job_type="send_interview",
                application_id=row.id,
                priority=0,
            )
            logger.info(
                "Queued interview send job",
                application_id=row.id,
                candidate=row.candidate_name,
                requisition=row.requisition_name,
            )

    async def _queue_evaluation_jobs(self) -> None:
        """Queue evaluation jobs for completed interviews."""
        query = text("""
            SELECT i.id as interview_id, i.application_id, a.candidate_name
            FROM interviews i
            JOIN applications a ON i.application_id = a.id
            WHERE i.status = 'completed'
              AND NOT EXISTS (
                  SELECT 1 FROM evaluations e WHERE e.interview_id = i.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = i.application_id
                    AND j.job_type = 'evaluate'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()  # Must fetch all before executing another query

        for row in rows:
            self.queue.enqueue(
                job_type="evaluate",
                application_id=row.application_id,
                priority=0,
                payload={"interview_id": row.interview_id},
            )
            logger.info(
                "Queued evaluation job",
                interview_id=row.interview_id,
                application_id=row.application_id,
                candidate=row.candidate_name,
            )

    async def _queue_report_jobs(self) -> None:
        """Queue report generation jobs for evaluated applications."""
        query = text("""
            SELECT a.id, a.candidate_name, i.id as interview_id
            FROM applications a
            JOIN interviews i ON i.application_id = a.id
            JOIN evaluations e ON e.interview_id = i.id
            WHERE a.status = 'interview_complete'
              AND NOT EXISTS (
                  SELECT 1 FROM reports rep WHERE rep.application_id = a.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'generate_report'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)
        rows = result.fetchall()  # Must fetch all before executing another query

        for row in rows:
            self.queue.enqueue(
                job_type="generate_report",
                application_id=row.id,
                priority=0,
            )
            logger.info(
                "Queued report generation job",
                application_id=row.id,
                candidate=row.candidate_name,
            )

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "interval": self.interval,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }
