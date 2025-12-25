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
        self.lookback_hours = settings.LOOKBACK_HOURS_DEFAULT
        self.last_run: Optional[datetime] = None

    async def run(self) -> None:
        """Main scheduler loop."""
        self.running = True
        logger.info(
            "Scheduler started",
            interval=self.interval,
            lookback_hours=self.lookback_hours,
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

        # 1. Check for active requisitions that need syncing
        await self._queue_sync_jobs()

        # 2. Check for applications needing analysis
        await self._queue_analysis_jobs()

        # 3. Check for analyzed applications ready for interview (auto-send)
        await self._queue_interview_jobs()

        # 4. Check for completed interviews needing evaluation
        await self._queue_evaluation_jobs()

        # 5. Check for evaluated interviews needing reports
        await self._queue_report_jobs()

    async def _queue_sync_jobs(self) -> None:
        """Queue sync jobs for active requisitions."""
        # Get active requisitions that haven't been synced recently
        lookback = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        query = text("""
            SELECT r.id, r.external_id, r.name
            FROM requisitions r
            WHERE r.is_active = 1
              AND r.sync_enabled = 1
              AND (r.last_synced_at IS NULL OR r.last_synced_at < :lookback)
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.requisition_id = r.id
                    AND j.job_type = 'sync'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query, {"lookback": lookback})

        for row in result:
            self.queue.enqueue(
                job_type="sync",
                requisition_id=row.id,
                priority=0,
            )
            logger.info("Queued sync job", requisition_id=row.id, requisition_name=row.name)

    async def _queue_analysis_jobs(self) -> None:
        """Queue analysis jobs for new applications."""
        query = text("""
            SELECT a.id, a.candidate_name
            FROM applications a
            WHERE a.status = 'new'
              AND a.artifacts IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = a.id
                    AND j.job_type = 'analyze'
                    AND j.status IN ('pending', 'running')
              )
        """)

        result = self.db.execute(query)

        for row in result:
            self.queue.enqueue(
                job_type="analyze",
                application_id=row.id,
                priority=0,
            )
            logger.info("Queued analysis job", application_id=row.id, candidate=row.candidate_name)

    async def _queue_interview_jobs(self) -> None:
        """Queue interview send jobs for analyzed applications with auto-send enabled."""
        query = text("""
            SELECT a.id, a.candidate_name, r.name as requisition_name
            FROM applications a
            JOIN requisitions r ON a.requisition_id = r.id
            WHERE a.status = 'analyzed'
              AND r.auto_send_interview = 1
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

        result = self.db.execute(query)

        for row in result:
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

        for row in result:
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

        for row in result:
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
            "lookback_hours": self.lookback_hours,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }
