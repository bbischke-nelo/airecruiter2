"""SES integration for sending emails."""

import os
from pathlib import Path
from typing import List, Optional

import boto3
import structlog
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.orm import Session

from processor.config import settings

logger = structlog.get_logger()

# Template directory - relative to project root
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "api" / "config" / "templates"


class SESService:
    """Service for sending emails via AWS SES."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize SES client with SES-specific credentials.

        Args:
            db: Optional database session for fetching email templates
        """
        client_kwargs = {"region_name": settings.SES_REGION}
        if settings.SES_ACCESS_KEY_ID and settings.SES_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.SES_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.SES_SECRET_ACCESS_KEY
        self.client = boto3.client("ses", **client_kwargs)
        self.from_email = settings.SES_FROM_EMAIL
        self.from_name = settings.SES_FROM_NAME
        self.db = db

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

    def _load_template(self, name: str) -> str:
        """Load a template file by name.

        Args:
            name: Template filename (e.g., 'interview_email.html')

        Returns:
            Template content as string
        """
        template_path = TEMPLATE_DIR / name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _render_template(self, template: str, **kwargs) -> str:
        """Render a template with variable substitution.

        Uses {{variable}} syntax for placeholders.

        Args:
            template: Template string with {{placeholders}}
            **kwargs: Variables to substitute

        Returns:
            Rendered template
        """
        result = template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    async def send_interview_invite(
        self,
        to: str,
        candidate_name: str,
        position: str,
        interview_url: str,
        recruiter_name: Optional[str] = None,
        recruiter_email: Optional[str] = None,
        expires_in_days: int = 7,
        company_name: str = "CrossCountry Freight Solutions",
        logo_url: Optional[str] = None,
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
            company_name: Company name for branding
            logo_url: URL to company logo (use logo-white.png for dark header)

        Returns:
            SES message ID
        """
        subject = f"Interview Invitation: {position} at {company_name}"
        first_name = candidate_name.split()[0] if candidate_name else "there"

        # Default logo URL - use CCFS recruiter app
        if not logo_url:
            logo_url = "https://admin.ccfs.com/recruiter2/logo-primary.png"

        # Template variables
        template_vars = {
            "company_name": company_name,
            "first_name": first_name,
            "position": position,
            "interview_url": interview_url,
            "expires_in_days": expires_in_days,
            "recruiter_name": recruiter_name or "The Talent Team",
            "logo_url": logo_url,
        }

        # Load and render templates
        html_template = self._load_template("interview_email.html")
        text_template = self._load_template("interview_email.txt")

        html_body = self._render_template(html_template, **template_vars)
        text_body = self._render_template(text_template, **template_vars)

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
