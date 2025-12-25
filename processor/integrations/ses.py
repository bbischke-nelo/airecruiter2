"""SES integration for sending emails."""

from typing import List, Optional

import boto3
import structlog
from botocore.exceptions import ClientError

from processor.config import settings

logger = structlog.get_logger()


class SESService:
    """Service for sending emails via AWS SES."""

    def __init__(self):
        """Initialize SES client."""
        self.client = boto3.client("ses", region_name=settings.SES_REGION)
        self.from_email = settings.SES_FROM_EMAIL
        self.from_name = settings.SES_FROM_NAME

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> str:
        """Send an email via SES.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional, derived from HTML if not provided)
            reply_to: Reply-to address
            cc: CC addresses
            bcc: BCC addresses

        Returns:
            SES message ID
        """
        try:
            # Build source with display name
            source = f"{self.from_name} <{self.from_email}>"

            # Build destination
            destination = {"ToAddresses": [to]}
            if cc:
                destination["CcAddresses"] = cc
            if bcc:
                destination["BccAddresses"] = bcc

            # Build message body
            body = {"Html": {"Data": html_body, "Charset": "utf-8"}}
            if text_body:
                body["Text"] = {"Data": text_body, "Charset": "utf-8"}

            # Build message
            message = {
                "Subject": {"Data": subject, "Charset": "utf-8"},
                "Body": body,
            }

            # Send
            params = {
                "Source": source,
                "Destination": destination,
                "Message": message,
            }
            if reply_to:
                params["ReplyToAddresses"] = [reply_to]

            response = self.client.send_email(**params)

            message_id = response["MessageId"]

            logger.info(
                "Email sent",
                message_id=message_id,
                to=to,
                subject=subject,
            )

            return message_id

        except ClientError as e:
            logger.error("SES send failed", error=str(e), to=to)
            raise SESError(f"Email send failed: {str(e)}") from e

    async def send_interview_invite(
        self,
        to: str,
        candidate_name: str,
        position: str,
        interview_url: str,
        recruiter_name: Optional[str] = None,
        recruiter_email: Optional[str] = None,
        expires_in_days: int = 7,
    ) -> str:
        """Send an interview invitation email.

        Args:
            to: Candidate email
            candidate_name: Candidate's name
            position: Job position title
            interview_url: Link to start interview
            recruiter_name: Recruiter's name for reply-to
            recruiter_email: Recruiter's email for reply-to
            expires_in_days: Days until link expires

        Returns:
            SES message ID
        """
        subject = f"Interview Invitation - {position}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #0F5A9C; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Interview Invitation</h1>
    </div>

    <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px;">
        <p>Dear {candidate_name},</p>

        <p>Thank you for your interest in the <strong>{position}</strong> position. We were impressed with your application and would like to invite you to complete a brief screening interview.</p>

        <p>This is an AI-assisted interview that you can complete at your convenience. The interview typically takes 10-15 minutes and allows you to share more about your experience and qualifications.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{interview_url}" style="background-color: #0F5A9C; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Start Your Interview</a>
        </div>

        <p style="color: #666; font-size: 14px;">This link will expire in {expires_in_days} days. If you have any questions or need assistance, please don't hesitate to reach out.</p>

        <p>We look forward to learning more about you!</p>

        <p>Best regards,<br>
        {recruiter_name or "The Recruiting Team"}</p>
    </div>

    <div style="text-align: center; padding: 20px; color: #888; font-size: 12px;">
        <p>This is an automated message. Please do not reply directly to this email.</p>
    </div>
</body>
</html>
"""

        text_body = f"""
Dear {candidate_name},

Thank you for your interest in the {position} position. We were impressed with your application and would like to invite you to complete a brief screening interview.

This is an AI-assisted interview that you can complete at your convenience. The interview typically takes 10-15 minutes.

To start your interview, please visit:
{interview_url}

This link will expire in {expires_in_days} days.

Best regards,
{recruiter_name or "The Recruiting Team"}
"""

        return await self.send_email(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to=recruiter_email,
        )

    async def send_interview_complete_notification(
        self,
        to: str,
        candidate_name: str,
        position: str,
        application_url: str,
    ) -> str:
        """Send notification to recruiter when interview is complete.

        Args:
            to: Recruiter email
            candidate_name: Candidate's name
            position: Job position title
            application_url: Link to view application

        Returns:
            SES message ID
        """
        subject = f"Interview Complete - {candidate_name} for {position}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #0F5A9C; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Interview Completed</h1>
    </div>

    <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px;">
        <p><strong>{candidate_name}</strong> has completed their AI interview for the <strong>{position}</strong> position.</p>

        <p>The interview has been evaluated and a candidate report is being generated.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{application_url}" style="background-color: #0F5A9C; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View Application</a>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=to,
            subject=subject,
            html_body=html_body,
        )


class SESError(Exception):
    """Raised when SES operations fail."""

    pass
