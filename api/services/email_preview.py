"""Email preview service for generating email previews without sending.

Used for the 2-step interview send flow where recruiters can preview
and optionally modify the email before sending.
"""

from typing import Optional

from api.schemas.interviews import EmailPreview

# CCFS brand colors (from ccfs.com)
CCFS_RED = "#C6232B"
CCFS_RED_DARK = "#A01D24"
CCFS_BLUE = "#27AAE1"  # Accent color


def generate_interview_email_preview(
    candidate_email: str,
    candidate_name: str,
    position_title: str,
    interview_url: str,
    recruiter_name: Optional[str] = None,
    expiry_days: int = 7,
    company_name: str = "CrossCountry Freight Solutions",
    logo_url: Optional[str] = None,
) -> EmailPreview:
    """Generate email preview for interview invitation.

    This generates the same email that would be sent via SES,
    but returns it for preview instead of sending.

    Uses human factors engineering principles:
    - Clear value proposition and benefits
    - Personalization and warm professional tone
    - Strong but friendly call-to-action
    - Low friction messaging (convenience, short duration)
    - Social proof and credibility indicators
    - Accessible design with good contrast

    Args:
        candidate_email: Recipient email
        candidate_name: Candidate's name
        position_title: Job position title
        interview_url: Link to start interview
        recruiter_name: Recruiter's name for signature
        expiry_days: Days until link expires
        company_name: Company name for branding

    Returns:
        EmailPreview with subject and body_html
    """
    # Subject line: Company name for trust, personal, action-oriented
    subject = f"Interview Invitation: {position_title} at {company_name}"

    # Get first name for more personal greeting
    first_name = candidate_name.split()[0] if candidate_name else "there"

    # Default to CCFS logo from recruiter app
    if not logo_url:
        logo_url = "https://admin.ccfs.com/recruiter2/logo-primary.png"

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interview Invitation</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f4f4f4;">
    <!-- Wrapper table for email client compatibility -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f4f4;">
        <tr>
            <td align="center" style="padding: 20px 10px;">
                <!-- Main content container -->
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">

                    <!-- Header with logo/branding -->
                    <tr>
                        <td style="border-top: 4px solid {CCFS_RED}; background-color: #ffffff; padding: 30px 40px; text-align: center; border-radius: 12px 12px 0 0;">
                            <img src="{logo_url}" alt="{company_name}" style="max-width: 260px; height: auto;" />
                        </td>
                    </tr>

                    <!-- Next step banner -->
                    <tr>
                        <td style="background-color: #f0f7ff; padding: 16px 40px; border-bottom: 1px solid #d0e3f7;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="font-size: 15px; color: #1a5490;">
                                        <strong>Next step:</strong> Complete a brief digital interview
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Main content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="font-size: 18px; color: #333333; margin: 0 0 20px 0;">
                                Hi {first_name},
                            </p>

                            <p style="font-size: 16px; color: #444444; margin: 0 0 20px 0;">
                                Thank you for your interest in the <strong style="color: {CCFS_RED};">{position_title}</strong> position. We'd like to learn more about you as part of our hiring process.
                            </p>

                            <p style="font-size: 15px; color: #444444; margin: 0 0 20px 0;">
                                You'll answer a few questions through our digital interview platform &mdash; no video call or scheduling required. Just click the button below when you're ready.
                            </p>

                            <!-- Progress indicator -->
                            <p style="font-size: 13px; color: #666666; margin: 0 0 20px 0; text-align: center;">
                                <span style="background-color: #fce4e5; padding: 6px 14px; border-radius: 20px; color: {CCFS_RED}; font-weight: 500;">
                                    Step 2 of 4: Digital Interview
                                </span>
                            </p>

                            <!-- Value proposition box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 25px 0;">
                                <tr>
                                    <td style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; border-left: 4px solid {CCFS_RED};">
                                        <p style="font-size: 15px; color: #333333; margin: 0 0 12px 0; font-weight: 600;">
                                            What to expect:
                                        </p>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 4px 0; font-size: 14px; color: #555555;">
                                                    <span style="color: {CCFS_RED}; margin-right: 8px;">&#9679;</span>
                                                    <strong>Complete on your schedule</strong> &mdash; anytime, from any device
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 4px 0; font-size: 14px; color: #555555;">
                                                    <span style="color: {CCFS_RED}; margin-right: 8px;">&#9679;</span>
                                                    <strong>Only 10-15 minutes</strong> &mdash; a few straightforward questions
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 4px 0; font-size: 14px; color: #555555;">
                                                    <span style="color: {CCFS_RED}; margin-right: 8px;">&#9679;</span>
                                                    <strong>Review before submitting</strong> &mdash; no pressure, take your time
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Primary CTA button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center" style="padding: 10px 0 30px 0;">
                                        <a href="{interview_url}"
                                           style="display: inline-block; background: linear-gradient(135deg, {CCFS_RED} 0%, {CCFS_RED_DARK} 100%); color: #ffffff; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 16px; box-shadow: 0 4px 12px rgba(198, 35, 43, 0.3); transition: all 0.2s;">
                                            Start Your Interview &rarr;
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Urgency/expiry notice (soft) -->
                            <p style="font-size: 14px; color: #666666; margin: 0 0 25px 0; text-align: center;">
                                <span style="background-color: #fff3cd; padding: 4px 12px; border-radius: 4px; color: #856404;">
                                    This link is valid for {expiry_days} days
                                </span>
                            </p>

                            <!-- What happens next -->
                            <p style="font-size: 15px; color: #444444; margin: 0 0 20px 0;">
                                <strong>What happens next?</strong> After you complete the interview, our team will review your responses and reach out about next steps within a few business days.
                            </p>

                            <!-- Reassurance & Compliance -->
                            <p style="font-size: 15px; color: #444444; margin: 0 0 12px 0;">
                                Questions? We're here to help make this process as smooth as possible.
                            </p>
                            <p style="font-size: 13px; color: #666666; margin: 0 0 20px 0; padding: 10px; background-color: #fafafa; border-radius: 4px;">
                                <strong>Need an accommodation?</strong> If you require a reasonable accommodation to complete this interview due to a disability, please contact us at <a href="mailto:jobs@ccfs.com" style="color: {CCFS_BLUE};">jobs@ccfs.com</a> or call <strong>(800) 521-0287</strong> and we'll be happy to assist.
                            </p>

                            <!-- Signature -->
                            <p style="font-size: 15px; color: #333333; margin: 25px 0 0 0;">
                                Looking forward to connecting with you,
                            </p>
                            <p style="font-size: 15px; color: #333333; margin: 5px 0 0 0;">
                                <strong>{recruiter_name or "The Talent Team"}</strong><br>
                                <span style="color: #666666; font-size: 14px;">{company_name}</span><br>
                                <span style="color: #666666; font-size: 13px;"><a href="mailto:jobs@ccfs.com" style="color: {CCFS_BLUE};">jobs@ccfs.com</a> &bull; (800) 521-0287</span>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 25px 40px; border-top: 1px solid #e9ecef; border-radius: 0 0 12px 12px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="text-align: center;">
                                        <p style="font-size: 12px; color: #555555; margin: 0 0 12px 0;">
                                            <strong>Important:</strong> This interview uses artificial intelligence (AI) technology. Your responses will be recorded and reviewed as part of our hiring process.
                                        </p>
                                        <p style="font-size: 11px; color: #888888; margin: 0 0 12px 0;">
                                            {company_name} is an equal opportunity employer. We do not discriminate based on race, color, religion, sex, national origin, age, disability, veteran status, sexual orientation, gender identity, or any other protected characteristic.
                                        </p>
                                        <p style="font-size: 12px; color: #888888; margin: 0 0 8px 0;">
                                            Having trouble with the link? Copy and paste this URL into your browser:<br>
                                            <a href="{interview_url}" style="color: {CCFS_BLUE}; word-break: break-all; font-size: 11px;">{interview_url}</a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    return EmailPreview(
        to_email=candidate_email,
        subject=subject,
        body_html=html_body,
    )
