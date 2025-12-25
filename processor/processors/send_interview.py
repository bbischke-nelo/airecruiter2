"""Send interview processor for interview invitations."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.processors.base import BaseProcessor
from processor.queue_manager import QueueManager
from processor.integrations.ses import SESService
from processor.config import settings

logger = structlog.get_logger()


class SendInterviewProcessor(BaseProcessor):
    """Sends interview invitation emails."""

    job_type = "send_interview"

    def __init__(self, db: Session, queue: QueueManager):
        super().__init__(db, queue)
        self.ses = SESService()

    async def process(
        self,
        application_id: Optional[int] = None,
        requisition_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Process a send interview job.

        Args:
            application_id: Application to send interview for
            requisition_id: Not used
            payload: Additional options (e.g., expires_days)
        """
        if not application_id:
            raise ValueError("application_id is required for send_interview")

        self.logger.info("Sending interview invitation", application_id=application_id)

        # Get application details
        query = text("""
            SELECT a.id, a.candidate_name, a.candidate_email, a.requisition_id,
                   r.name as position, r.recruiter_id,
                   rec.email as recruiter_email, rec.name as recruiter_name
            FROM applications a
            JOIN requisitions r ON a.requisition_id = r.id
            LEFT JOIN recruiters rec ON r.recruiter_id = rec.id
            WHERE a.id = :app_id
        """)
        result = self.db.execute(query, {"app_id": application_id})
        app = result.fetchone()

        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Check if interview already exists
        existing = self.db.execute(
            text("SELECT id FROM interviews WHERE application_id = :app_id"),
            {"app_id": application_id},
        ).fetchone()

        if existing:
            self.logger.warning(
                "Interview already exists",
                application_id=application_id,
                interview_id=existing.id,
            )
            return

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_days = (payload or {}).get("expires_days", 7)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        # Create interview record
        insert_query = text("""
            INSERT INTO interviews (application_id, token, token_expires_at,
                                   status, created_at)
            OUTPUT INSERTED.id
            VALUES (:app_id, :token, :expires_at, 'scheduled', GETUTCDATE())
        """)
        result = self.db.execute(
            insert_query,
            {
                "app_id": application_id,
                "token": token,
                "expires_at": expires_at,
            },
        )
        # Must fetch before commit with pyodbc
        interview_id = result.scalar()
        self.db.commit()

        # Build interview URL
        interview_url = f"{settings.FRONTEND_URL}/interview/{token}"

        # Send email
        message_id = await self.ses.send_interview_invite(
            to=app.candidate_email,
            candidate_name=app.candidate_name,
            position=app.position,
            interview_url=interview_url,
            recruiter_name=app.recruiter_name,
            recruiter_email=app.recruiter_email,
            expires_in_days=expires_days,
        )

        # Update application status
        update_query = text("""
            UPDATE applications
            SET status = 'interview_pending',
                interview_sent = 1,
                interview_sent_at = GETUTCDATE(),
                updated_at = GETUTCDATE()
            WHERE id = :app_id
        """)
        self.db.execute(update_query, {"app_id": application_id})
        self.db.commit()

        # Log email
        await self._log_email(
            application_id=application_id,
            email_type="interview_invite",
            to_email=app.candidate_email,
            message_id=message_id,
        )

        # Log activity
        self.log_activity(
            action="interview_sent",
            application_id=application_id,
            requisition_id=app.requisition_id,
            details={
                "interview_id": interview_id,
                "expires_at": expires_at.isoformat(),
                "message_id": message_id,
            },
        )

        self.logger.info(
            "Interview invitation sent",
            application_id=application_id,
            interview_id=interview_id,
            candidate=app.candidate_name,
        )

    async def _log_email(
        self,
        application_id: int,
        email_type: str,
        to_email: str,
        message_id: str,
    ) -> None:
        """Log email in email_log table."""
        query = text("""
            INSERT INTO email_log (application_id, email_type, to_email,
                                  message_id, status, sent_at)
            VALUES (:app_id, :type, :to, :msg_id, 'sent', GETUTCDATE())
        """)
        self.db.execute(
            query,
            {
                "app_id": application_id,
                "type": email_type,
                "to": to_email,
                "msg_id": message_id,
            },
        )
        self.db.commit()
