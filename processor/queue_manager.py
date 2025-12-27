"""Queue manager for reliable job execution with SQL Server."""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.config import settings

logger = structlog.get_logger()


class QueueManager:
    """Manages the job queue with SQL Server row locking."""

    def __init__(self, db: Session):
        self.db = db
        self.max_attempts = settings.QUEUE_MAX_ATTEMPTS
        self.retry_base_delay = settings.QUEUE_RETRY_BASE_DELAY

    def enqueue(
        self,
        job_type: str,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        priority: int = 0,
        scheduled_for: Optional[datetime] = None,
        payload: Optional[dict] = None,
    ) -> int:
        """Add a job to the queue.

        Args:
            job_type: Type of job (sync, analyze, send_interview, evaluate, generate_report, upload_report)
            application_id: Associated application ID
            requisition_id: Associated requisition ID
            priority: Higher = processed first (default 0)
            scheduled_for: When to process (default now)
            payload: Additional job data as JSON

        Returns:
            Job ID
        """
        if scheduled_for is None:
            scheduled_for = datetime.now(timezone.utc)

        query = text("""
            INSERT INTO jobs (job_type, application_id, requisition_id, priority, status,
                            payload, attempts, max_attempts, scheduled_for, created_at)
            OUTPUT INSERTED.id
            VALUES (:job_type, :application_id, :requisition_id, :priority, 'pending',
                    :payload, 0, :max_attempts, :scheduled_for, GETUTCDATE())
        """)

        result = self.db.execute(
            query,
            {
                "job_type": job_type,
                "application_id": application_id,
                "requisition_id": requisition_id,
                "priority": priority,
                "payload": json.dumps(payload) if payload else None,
                "max_attempts": self.max_attempts,
                "scheduled_for": scheduled_for,
            },
        )
        # Must fetch before commit with pyodbc
        job_id = result.scalar()
        self.db.commit()
        logger.info(
            "Job enqueued",
            job_id=job_id,
            job_type=job_type,
            application_id=application_id,
            requisition_id=requisition_id,
        )
        return job_id

    def claim_next(self) -> Optional[dict]:
        """Claim the next pending job using row locking.

        Uses UPDLOCK and READPAST for safe concurrent claiming.

        Returns:
            Job data dict or None if no jobs available
        """
        # Step 1: Find and lock the next pending job
        select_query = text("""
            SELECT TOP(1) id FROM jobs WITH (UPDLOCK, READPAST)
            WHERE status = 'pending'
              AND scheduled_for <= GETUTCDATE()
            ORDER BY priority DESC, created_at ASC
        """)

        result = self.db.execute(select_query)
        row = result.fetchone()

        if not row:
            return None

        job_id = row.id

        # Step 2: Update the job status and get full job data
        update_query = text("""
            UPDATE jobs
            SET status = 'running',
                started_at = GETUTCDATE(),
                attempts = attempts + 1
            WHERE id = :job_id
        """)
        self.db.execute(update_query, {"job_id": job_id})

        # Step 3: Fetch the updated job data
        fetch_query = text("""
            SELECT id, job_type, application_id, requisition_id, priority,
                   payload, attempts, max_attempts, created_at, scheduled_for
            FROM jobs
            WHERE id = :job_id
        """)
        result = self.db.execute(fetch_query, {"job_id": job_id})
        row = result.fetchone()  # Must fetch BEFORE commit with pyodbc
        self.db.commit()

        if not row:
            return None

        job = {
            "id": row.id,
            "job_type": row.job_type,
            "application_id": row.application_id,
            "requisition_id": row.requisition_id,
            "priority": row.priority,
            "payload": json.loads(row.payload) if row.payload else None,
            "attempts": row.attempts,
            "max_attempts": row.max_attempts,
            "created_at": row.created_at,
            "scheduled_for": row.scheduled_for,
        }

        logger.info(
            "Job claimed",
            job_id=job["id"],
            job_type=job["job_type"],
            attempt=job["attempts"],
        )
        return job

    def complete(self, job_id: int) -> None:
        """Mark a job as completed and remove from queue."""
        query = text("""
            UPDATE jobs
            SET status = 'completed', completed_at = GETUTCDATE()
            WHERE id = :job_id
        """)
        self.db.execute(query, {"job_id": job_id})
        self.db.commit()

        logger.info("Job completed", job_id=job_id)

    def fail(self, job_id: int, error: str) -> None:
        """Mark a job as failed, schedule retry or move to dead letter.

        Uses exponential backoff: base_delay * 2^(attempts-1)
        """
        # Get current job state
        query = text("SELECT attempts, max_attempts FROM jobs WHERE id = :job_id")
        result = self.db.execute(query, {"job_id": job_id})
        row = result.fetchone()

        if not row:
            logger.error("Job not found for failure", job_id=job_id)
            return

        attempts = row.attempts or 0
        max_attempts = row.max_attempts or 3  # Default to 3 retries

        if attempts >= max_attempts:
            # Move to dead letter
            query = text("""
                UPDATE jobs
                SET status = 'dead',
                    last_error = :error,
                    completed_at = GETUTCDATE()
                WHERE id = :job_id
            """)
            self.db.execute(query, {"job_id": job_id, "error": error})
            logger.warning("Job moved to dead letter", job_id=job_id, error=error)
        else:
            # Schedule retry with exponential backoff
            delay_seconds = self.retry_base_delay * (2 ** (attempts - 1))
            next_attempt = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

            query = text("""
                UPDATE jobs
                SET status = 'pending',
                    last_error = :error,
                    scheduled_for = :next_attempt,
                    started_at = NULL
                WHERE id = :job_id
            """)
            self.db.execute(
                query,
                {"job_id": job_id, "error": error, "next_attempt": next_attempt},
            )
            logger.info(
                "Job scheduled for retry",
                job_id=job_id,
                attempt=attempts,
                next_attempt=next_attempt.isoformat(),
            )

        self.db.commit()

    def get_status(self) -> dict:
        """Get queue status counts."""
        query = text("""
            SELECT
                status,
                COUNT(*) as count
            FROM jobs
            GROUP BY status
        """)
        result = self.db.execute(query)

        status = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "dead": 0}
        for row in result:
            status[row.status] = row.count

        return status

    def get_pending_count(self) -> int:
        """Get count of pending jobs."""
        query = text("SELECT COUNT(*) FROM jobs WHERE status = 'pending'")
        result = self.db.execute(query)
        return result.scalar() or 0

    def get_running_jobs(self) -> List[dict]:
        """Get currently running jobs."""
        query = text("""
            SELECT id, job_type, application_id, requisition_id,
                   attempts, started_at
            FROM jobs
            WHERE status = 'running'
            ORDER BY started_at
        """)
        result = self.db.execute(query)

        return [
            {
                "id": row.id,
                "job_type": row.job_type,
                "application_id": row.application_id,
                "requisition_id": row.requisition_id,
                "attempts": row.attempts,
                "started_at": row.started_at,
            }
            for row in result
        ]

    def retry_dead_job(self, job_id: int) -> bool:
        """Retry a dead letter job."""
        query = text("""
            UPDATE jobs
            SET status = 'pending',
                attempts = 0,
                last_error = NULL,
                scheduled_for = GETUTCDATE(),
                started_at = NULL,
                completed_at = NULL
            WHERE id = :job_id AND status = 'dead'
        """)
        result = self.db.execute(query, {"job_id": job_id})
        self.db.commit()

        if result.rowcount > 0:
            logger.info("Dead job retried", job_id=job_id)
            return True
        return False

    def clear_completed(self, older_than_hours: int = 24) -> int:
        """Clear completed jobs older than specified hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

        query = text("""
            DELETE FROM jobs
            WHERE status = 'completed' AND completed_at < :cutoff
        """)
        result = self.db.execute(query, {"cutoff": cutoff})
        self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.info("Cleared completed jobs", count=count, older_than_hours=older_than_hours)
        return count

    def recover_orphaned_interviews(self) -> int:
        """Find completed interviews without evaluation jobs and create them.

        This catches interviews that completed but didn't get an evaluate job
        queued (e.g., due to crashes, bugs, or missing code paths).

        Returns:
            Number of evaluate jobs created
        """
        # Find completed interviews without any evaluate job (pending, running, completed, or dead)
        query = text("""
            INSERT INTO jobs (job_type, application_id, priority, status,
                            attempts, max_attempts, scheduled_for, created_at)
            SELECT 'evaluate', i.application_id, 5, 'pending',
                   0, :max_attempts, GETUTCDATE(), GETUTCDATE()
            FROM interviews i
            WHERE i.status = 'completed'
              AND i.completed_at IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = i.application_id
                    AND j.job_type = 'evaluate'
              )
              -- Only recover interviews completed more than 5 minutes ago
              -- (gives normal flow time to create the job)
              AND i.completed_at < DATEADD(MINUTE, -5, GETUTCDATE())
        """)

        result = self.db.execute(query, {"max_attempts": self.max_attempts})
        self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.warning("Recovered orphaned interviews", count=count)
        return count

    def recover_stuck_jobs(self, stuck_threshold_minutes: int = 30) -> int:
        """Reset jobs stuck in 'running' status back to 'pending'.

        Jobs can get stuck if a worker crashes mid-processing.

        Args:
            stuck_threshold_minutes: Minutes after which a running job is considered stuck

        Returns:
            Number of jobs recovered
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stuck_threshold_minutes)

        query = text("""
            UPDATE jobs
            SET status = 'pending',
                started_at = NULL,
                last_error = 'Recovered from stuck state (worker likely crashed)'
            WHERE status = 'running'
              AND started_at < :cutoff
        """)
        result = self.db.execute(query, {"cutoff": cutoff})
        self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.warning("Recovered stuck jobs", count=count, threshold_minutes=stuck_threshold_minutes)
        return count

    def recover_expired_interviews(self) -> int:
        """Find expired interviews with content and create evaluation jobs.

        Catches interviews that:
        - Were started (have messages) but token expired before completion
        - Are still in 'in_progress' or 'scheduled' status with expired tokens

        Returns:
            Number of evaluate jobs created
        """
        # First, mark expired interviews as 'expired' status
        mark_expired_query = text("""
            UPDATE interviews
            SET status = 'expired',
                completed_at = GETUTCDATE()
            WHERE status IN ('in_progress', 'scheduled')
              AND token_expires_at IS NOT NULL
              AND token_expires_at < GETUTCDATE()
              AND started_at IS NOT NULL
        """)
        self.db.execute(mark_expired_query)
        self.db.commit()

        # Now create evaluate jobs for expired interviews with messages
        query = text("""
            INSERT INTO jobs (job_type, application_id, priority, status,
                            attempts, max_attempts, scheduled_for, created_at)
            SELECT 'evaluate', i.application_id, 5, 'pending',
                   0, :max_attempts, GETUTCDATE(), GETUTCDATE()
            FROM interviews i
            WHERE i.status = 'expired'
              AND i.started_at IS NOT NULL
              -- Must have at least one user message to evaluate
              AND EXISTS (
                  SELECT 1 FROM messages m
                  WHERE m.interview_id = i.id
                    AND m.role = 'user'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.application_id = i.application_id
                    AND j.job_type = 'evaluate'
              )
              -- Only process interviews expired more than 5 minutes ago
              AND i.token_expires_at < DATEADD(MINUTE, -5, GETUTCDATE())
        """)

        result = self.db.execute(query, {"max_attempts": self.max_attempts})
        self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.warning("Recovered expired interviews for evaluation", count=count)
        return count

    def recover_stuck_applications(self, stuck_threshold_minutes: int = 15) -> int:
        """Recover applications stuck in transient statuses.

        Transient statuses should quickly transition to the next status.
        If they're stuck, it means a job failed or wasn't created.

        Args:
            stuck_threshold_minutes: Minutes after which an app is considered stuck

        Returns:
            Number of jobs created to recover stuck applications
        """
        total_recovered = 0

        # Recovery configs: (status, job_type, description)
        # These are statuses where a job should exist but might be missing
        recovery_configs = [
            ("new", "download_resume", "new apps needing resume download"),
            ("downloading", "download_resume", "downloading apps with no active job"),
            ("downloaded", "extract_facts", "downloaded apps needing extraction"),
            ("extracting", "extract_facts", "extracting apps with no active job"),
            ("extracted", "analyze", "extracted apps needing analysis"),
            ("generating_summary", "analyze", "generating_summary apps with no active job"),
            ("interview_complete", "generate_report", "interview_complete apps needing report"),
        ]

        for status, job_type, description in recovery_configs:
            query = text("""
                INSERT INTO jobs (job_type, application_id, priority, status,
                                attempts, max_attempts, scheduled_for, created_at)
                SELECT :job_type, a.id, 5, 'pending',
                       0, :max_attempts, GETUTCDATE(), GETUTCDATE()
                FROM applications a
                WHERE a.status = :status
                  AND a.updated_at < DATEADD(MINUTE, -:threshold, GETUTCDATE())
                  AND NOT EXISTS (
                      SELECT 1 FROM jobs j
                      WHERE j.application_id = a.id
                        AND j.job_type = :job_type
                        AND j.status IN ('pending', 'running')
                  )
            """)
            result = self.db.execute(
                query,
                {
                    "job_type": job_type,
                    "status": status,
                    "max_attempts": self.max_attempts,
                    "threshold": stuck_threshold_minutes,
                }
            )
            self.db.commit()
            count = result.rowcount
            if count > 0:
                logger.warning(f"Recovered stuck {description}", count=count)
            total_recovered += count

        return total_recovered
