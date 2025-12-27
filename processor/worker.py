"""Worker that executes jobs from the queue."""

import asyncio
import time
from typing import Dict, Type, Optional, Callable

import structlog
from sqlalchemy.orm import Session

from processor.config import settings
from processor.database import SessionLocal
from processor.queue_manager import QueueManager
from processor.processors.base import BaseProcessor

logger = structlog.get_logger()


class Worker:
    """Executes jobs from the queue with concurrency control.

    Uses a session factory to create fresh sessions per job to avoid
    concurrency issues with shared sessions.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        processors: Optional[Dict[str, Type[BaseProcessor]]] = None,
    ):
        """Initialize worker.

        Args:
            session_factory: Factory function that creates new DB sessions
            processors: Map of job_type -> processor class
        """
        self.session_factory = session_factory
        self.processors = processors or {}
        self.running = False
        self.active_jobs: Dict[int, asyncio.Task] = {}
        self.max_concurrency = settings.QUEUE_MAX_CONCURRENCY
        self.poll_interval = settings.QUEUE_POLL_INTERVAL

    def register_processor(self, processor_class: Type[BaseProcessor]) -> None:
        """Register a processor for a job type.

        Args:
            processor_class: Processor class with job_type attribute
        """
        self.processors[processor_class.job_type] = processor_class
        logger.info("Processor registered", job_type=processor_class.job_type)

    def _create_processor(self, job_type: str, db: Session) -> BaseProcessor:
        """Create a processor instance with its own session.

        Args:
            job_type: Type of job
            db: Database session for this processor

        Returns:
            Processor instance

        Raises:
            ValueError: If no processor registered for job type
        """
        if job_type not in self.processors:
            raise ValueError(f"No processor registered for job type: {job_type}")

        processor_class = self.processors[job_type]
        queue = QueueManager(db)
        return processor_class(db, queue)

    async def process_job(self, job: dict) -> None:
        """Process a single job with its own database session.

        Creates a fresh session for each job to avoid concurrency issues.

        Args:
            job: Job data from queue
        """
        job_id = job["id"]
        job_type = job["job_type"]

        # Create a fresh session for this job
        db = self.session_factory()
        try:
            processor = self._create_processor(job_type, db)

            logger.info(
                "Processing job",
                job_id=job_id,
                job_type=job_type,
                application_id=job.get("application_id"),
                requisition_id=job.get("requisition_id"),
            )

            await processor.process(
                application_id=job.get("application_id"),
                requisition_id=job.get("requisition_id"),
                payload=job.get("payload"),
            )

            # Use this job's session to mark complete
            queue = QueueManager(db)
            queue.complete(job_id)

        except Exception as e:
            logger.error(
                "Job failed",
                job_id=job_id,
                job_type=job_type,
                error=str(e),
                exc_info=True,
            )
            # Use this job's session to mark failed
            queue = QueueManager(db)
            queue.fail(job_id, str(e))

        finally:
            # Always close the session
            db.close()
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        self._last_maintenance = 0  # Track last maintenance run
        self._maintenance_interval = 60  # Run maintenance every 60 seconds

        logger.info(
            "Worker started",
            max_concurrency=self.max_concurrency,
            registered_processors=list(self.processors.keys()),
        )

        while self.running:
            # Clean up completed tasks
            completed = [
                job_id
                for job_id, task in self.active_jobs.items()
                if task.done()
            ]
            for job_id in completed:
                del self.active_jobs[job_id]

            # Run periodic maintenance (recover orphans, stuck jobs)
            now = time.time()
            if now - self._last_maintenance > self._maintenance_interval:
                self._last_maintenance = now
                await self._run_maintenance()

            # Check if we can take more jobs
            if len(self.active_jobs) >= self.max_concurrency:
                await asyncio.sleep(1)
                continue

            # Try to claim a job using a fresh session
            db = self.session_factory()
            try:
                queue = QueueManager(db)
                job = queue.claim_next()
            finally:
                db.close()

            if not job:
                await asyncio.sleep(self.poll_interval)
                continue

            # Start processing in background
            task = asyncio.create_task(self.process_job(job))
            self.active_jobs[job["id"]] = task

        logger.info("Worker stopped")

    async def _run_maintenance(self) -> None:
        """Run periodic maintenance tasks."""
        db = self.session_factory()
        try:
            queue = QueueManager(db)

            # Recover orphaned interviews (completed but no evaluate job)
            orphaned = queue.recover_orphaned_interviews()

            # Recover expired interviews (started but token expired, have content)
            expired = queue.recover_expired_interviews()

            # Recover stuck jobs (running for too long)
            stuck_jobs = queue.recover_stuck_jobs(stuck_threshold_minutes=30)

            # Recover applications stuck in transient statuses
            stuck_apps = queue.recover_stuck_applications(stuck_threshold_minutes=15)

            if orphaned > 0 or expired > 0 or stuck_jobs > 0 or stuck_apps > 0:
                logger.info(
                    "Maintenance completed",
                    orphaned_interviews=orphaned,
                    expired_interviews=expired,
                    stuck_jobs=stuck_jobs,
                    stuck_applications=stuck_apps,
                )
        except Exception as e:
            logger.error("Maintenance task failed", error=str(e))
        finally:
            db.close()

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self.running = False

        # Wait for active jobs to complete
        if self.active_jobs:
            logger.info("Waiting for active jobs to complete", count=len(self.active_jobs))
            await asyncio.gather(*self.active_jobs.values(), return_exceptions=True)

        logger.info("Worker shutdown complete")

    def get_status(self) -> dict:
        """Get worker status."""
        # Use a fresh session for status check
        db = self.session_factory()
        try:
            queue = QueueManager(db)
            queue_status = queue.get_status()
        finally:
            db.close()

        return {
            "running": self.running,
            "active_jobs": len(self.active_jobs),
            "max_concurrency": self.max_concurrency,
            "registered_processors": list(self.processors.keys()),
            "queue_status": queue_status,
        }
