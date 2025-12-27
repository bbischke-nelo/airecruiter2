"""SES integration for sending emails."""

from pathlib import Path
from typing import List, Optional

import boto3
import structlog
from botocore.exceptions import ClientError

from api.config.settings import settings

logger = structlog.get_logger()

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "config" / "templates"


class SESService:
    """Service for sending emails via AWS SES."""

    def __init__(self, from_email: Optional[str] = None, from_name: Optional[str] = None):
        """Initialize SES client.

        Args:
            from_email: Override sender email (defaults to settings.SES_FROM_EMAIL)
            from_name: Override sender name (defaults to settings.SES_FROM_NAME)
        """
        # Explicitly pass credentials if configured
        client_kwargs = {"region_name": settings.SES_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        self.client = boto3.client("ses", **client_kwargs)
        self.from_email = from_email or settings.SES_FROM_EMAIL
        self.from_name = from_name or settings.SES_FROM_NAME

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
            text_body: Plain text content (optional)
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
        """Load a template file by name."""
        template_path = TEMPLATE_DIR / name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _render_template(self, template: str, **kwargs) -> str:
        """Render a template with {{variable}} syntax."""
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
        """Send an interview invitation email."""
        subject = f"Interview Invitation: {position} at {company_name}"
        first_name = candidate_name.split()[0] if candidate_name else "there"

        # Default logo URL
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


class SESError(Exception):
    """Raised when SES operations fail."""
    pass
