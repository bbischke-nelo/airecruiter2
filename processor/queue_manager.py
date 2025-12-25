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
        self.db.commit()

        job_id = result.scalar()
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
        # SQL Server doesn't allow ORDER BY in UPDATE...OUTPUT
        # Use a subquery to select the ID first, then update by that ID
        query = text("""
            UPDATE jobs
            SET status = 'running',
                started_at = GETUTCDATE(),
                attempts = attempts + 1
            OUTPUT
                INSERTED.id,
                INSERTED.job_type,
                INSERTED.application_id,
                INSERTED.requisition_id,
                INSERTED.priority,
                INSERTED.payload,
                INSERTED.attempts,
                INSERTED.max_attempts,
                INSERTED.created_at,
                INSERTED.scheduled_for
            WHERE id = (
                SELECT TOP(1) id FROM jobs WITH (UPDLOCK, READPAST)
                WHERE status = 'pending'
                  AND scheduled_for <= GETUTCDATE()
                ORDER BY priority DESC, created_at ASC
            )
        """)

        result = self.db.execute(query)
        self.db.commit()

        row = result.fetchone()
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

        attempts, max_attempts = row.attempts, row.max_attempts

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
