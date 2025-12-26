"""Email preview service for generating email previews without sending.

Used for the 2-step interview send flow where recruiters can preview
and optionally modify the email before sending.
"""

from typing import Optional

from api.schemas.interviews import EmailPreview


def generate_interview_email_preview(
    candidate_email: str,
    candidate_name: str,
    position_title: str,
    interview_url: str,
    recruiter_name: Optional[str] = None,
    expiry_days: int = 7,
) -> EmailPreview:
    """Generate email preview for interview invitation.

    This generates the same email that would be sent via SES,
    but returns it for preview instead of sending.

    Args:
        candidate_email: Recipient email
        candidate_name: Candidate's name
        position_title: Job position title
        interview_url: Link to start interview
        recruiter_name: Recruiter's name for signature
        expiry_days: Days until link expires

    Returns:
        EmailPreview with subject and body_html
    """
    subject = f"Interview Invitation - {position_title}"

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

        <p>Thank you for your interest in the <strong>{position_title}</strong> position. We were impressed with your application and would like to invite you to complete a brief screening interview.</p>

        <p>This is an AI-assisted interview that you can complete at your convenience. The interview typically takes 10-15 minutes and allows you to share more about your experience and qualifications.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{interview_url}" style="background-color: #0F5A9C; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Start Your Interview</a>
        </div>

        <p style="color: #666; font-size: 14px;">This link will expire in {expiry_days} days. If you have any questions or need assistance, please don't hesitate to reach out.</p>

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

    return EmailPreview(
        to_email=candidate_email,
        subject=subject,
        body_html=html_body,
    )
