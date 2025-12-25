"""Base processor class for all job processors."""

from abc import ABC, abstractmethod
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from processor.queue_manager import QueueManager


class BaseProcessor(ABC):
    """Abstract base class for job processors."""

    # Override in subclasses
    job_type: str = "base"

    def __init__(self, db: Session, queue: QueueManager):
        """Initialize processor with database session and queue manager.

        Args:
            db: SQLAlchemy database session
            queue: Queue manager for enqueueing follow-up jobs
        """
        self.db = db
        self.queue = queue
        self.logger = structlog.get_logger().bind(processor=self.job_type)

    @abstractmethod
    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Process a job.

        Args:
            application_id: ID of the application to process
            requisition_id: ID of the requisition to process
            payload: Additional job data

        Raises:
            Exception: If processing fails (will be caught by worker for retry)
        """
        pass

    def log_activity(
        self,
        action: str,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log an activity to the activities table.

        Args:
            action: Action type (e.g., 'sync_completed', 'analysis_started')
            application_id: Associated application ID
            requisition_id: Associated requisition ID
            details: Additional details as JSON
        """
        import json
        from sqlalchemy import text

        query = text("""
            INSERT INTO activities (action, application_id, requisition_id, details, created_at)
            VALUES (:action, :application_id, :requisition_id, :details, GETUTCDATE())
        """)

        self.db.execute(
            query,
            {
                "action": action,
                "application_id": application_id,
                "requisition_id": requisition_id,
                "details": json.dumps(details) if details else None,
            },
        )
        self.db.commit()

    def enqueue_next(
        self,
        job_type: str,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        priority: int = 0,
        payload: Optional[dict] = None,
    ) -> int:
        """Enqueue a follow-up job.

        Args:
            job_type: Type of job to enqueue
            application_id: Associated application ID
            requisition_id: Associated requisition ID
            priority: Job priority
            payload: Additional job data

        Returns:
            New job ID
        """
        return self.queue.enqueue(
            job_type=job_type,
            application_id=application_id,
            requisition_id=requisition_id,
            priority=priority,
            payload=payload,
        )
