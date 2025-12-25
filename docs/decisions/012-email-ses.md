# ADR 012: Email via AWS SES

**Status:** Accepted
**Date:** 2025-01-15

## Context

airecruiter2 sends emails for:
- Interview invitations to candidates
- System alerts (credential failures, processing errors)
- (Future) Report delivery

## Decision

Use **AWS Simple Email Service (SES)** for all email delivery.

## Implementation

### Configuration

```bash
# Email settings
EMAIL_PROVIDER=ses
SES_REGION=us-east-1
SES_FROM_EMAIL=noreply@company.com
SES_FROM_NAME=AIRecruiter
SES_CONFIGURATION_SET=airecruiter2  # For tracking
```

### Email Service

```python
# api/services/email.py
import boto3
from botocore.exceptions import ClientError

class EmailService:
    def __init__(self):
        self.ses = boto3.client('ses', region_name=settings.SES_REGION)
        self.from_email = settings.SES_FROM_EMAIL
        self.from_name = settings.SES_FROM_NAME

    async def send_interview_invite(
        self,
        to_email: str,
        candidate_name: str,
        position: str,
        interview_url: str,
        recruiter: Recruiter,
    ) -> bool:
        template = await self.get_template('interview_invite')

        html_body = template.render(
            candidate_name=candidate_name,
            position=position,
            interview_url=interview_url,
            recruiter_name=recruiter.name,
            recruiter_contact=recruiter.public_contact_info,
        )

        return await self.send(
            to_email=to_email,
            subject=f"Interview Invitation: {position}",
            html_body=html_body,
        )

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str = None,
    ) -> bool:
        try:
            response = self.ses.send_email(
                Source=f"{self.from_name} <{self.from_email}>",
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': html_body},
                        'Text': {'Data': text_body or self.strip_html(html_body)},
                    },
                },
                ConfigurationSetName=settings.SES_CONFIGURATION_SET,
            )
            return True
        except ClientError as e:
            log.error("SES send failed", error=str(e), to=to_email)
            return False
```

### Email Templates

Stored in `email_templates` table or as files:

```
api/templates/email/
├── interview_invite.html
├── interview_invite.txt
├── alert_credential_failure.html
└── base.html
```

### Template Example

```html
<!-- interview_invite.html -->
{% extends "base.html" %}
{% block content %}
<p>Dear {{ candidate_name }},</p>

<p>Thank you for your interest in the <strong>{{ position }}</strong> role.</p>

<p>We'd like to invite you to complete a brief AI-assisted interview at your convenience.</p>

<p style="text-align: center;">
  <a href="{{ interview_url }}" class="button">Start Interview</a>
</p>

<p>This link will expire in 7 days.</p>

<p>If you have any questions, please contact:</p>
<pre>{{ recruiter_contact }}</pre>

<p>Best regards,<br>{{ recruiter_name }}</p>
{% endblock %}
```

## SES Setup

### Domain Verification

1. Add domain to SES
2. Add DKIM records to DNS
3. Verify domain ownership
4. (Production) Request production access

### IAM Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail"
            ],
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "ses:FromAddress": "noreply@company.com"
                }
            }
        }
    ]
}
```

## Tracking & Logging

### SES Configuration Set

Create a configuration set to track:
- Deliveries
- Bounces
- Complaints
- Opens (optional)
- Clicks (optional)

### Event Logging

```python
# Log all email attempts to email_log table
await db.create_email_log(
    to_email=to_email,
    template_id=template.id,
    subject=subject,
    application_id=application_id,
    status='sent',  # or 'failed'
    error=error_message if failed else None,
)
```

### Bounce Handling

Set up SNS topic for bounce notifications:

1. SES → SNS topic on bounce
2. SNS → Lambda or API endpoint
3. Mark email as bounced in `email_log`
4. (Optional) Flag candidate for review

## Consequences

### Positive

1. **Reliable**: SES has high deliverability
2. **Cheap**: ~$0.10 per 1000 emails
3. **Integrated**: Already using AWS
4. **Tracking**: Built-in delivery/bounce tracking

### Negative

1. **Sandbox mode**: Must request production access
2. **Sending limits**: Start at 200/day in sandbox
3. **Warmup**: Need to gradually increase volume

## Testing

### Sandbox Testing

SES starts in sandbox mode:
- Can only send to verified emails
- Add test emails to verified list

### Mailbox Simulator

Use SES mailbox simulator addresses:
- `success@simulator.amazonses.com` - Successful delivery
- `bounce@simulator.amazonses.com` - Hard bounce
- `complaint@simulator.amazonses.com` - Complaint
