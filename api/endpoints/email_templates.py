"""Email template management endpoints."""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import EmailTemplate
from api.schemas.base import CamelModel, PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()


# Schemas
class EmailTemplateCreate(CamelModel):
    name: str
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class EmailTemplateUpdate(CamelModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class EmailTemplateResponse(CamelModel):
    id: int
    name: str
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime]


@router.get("", response_model=PaginatedResponse[EmailTemplateResponse])
async def list_email_templates(
    template_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all email templates with optional filtering."""
    query = db.query(EmailTemplate)

    if template_type:
        query = query.filter(EmailTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(EmailTemplate.is_active == is_active)

    total = query.count()
    templates = (
        query.order_by(EmailTemplate.template_type, EmailTemplate.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = [EmailTemplateResponse.model_validate(t) for t in templates]

    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a specific email template."""
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return EmailTemplateResponse.model_validate(template)


@router.post("", response_model=EmailTemplateResponse, status_code=201)
async def create_email_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Create a new email template."""
    # If setting as default, unset other defaults of same type
    if data.is_default:
        db.query(EmailTemplate).filter(
            EmailTemplate.template_type == data.template_type,
            EmailTemplate.is_default == True,
        ).update({"is_default": False})

    template = EmailTemplate(
        name=data.name,
        template_type=data.template_type,
        subject=data.subject,
        body_html=data.body_html,
        body_text=data.body_text,
        is_active=data.is_active,
        is_default=data.is_default,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info("Email template created", id=template.id, name=template.name)
    return EmailTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: int,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Update an email template."""
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If setting as default, unset other defaults of same type
    if data.is_default:
        template_type = data.template_type or template.template_type
        db.query(EmailTemplate).filter(
            EmailTemplate.template_type == template_type,
            EmailTemplate.is_default == True,
            EmailTemplate.id != template_id,
        ).update({"is_default": False})

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    logger.info("Email template updated", id=template.id)
    return EmailTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204)
async def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Delete an email template."""
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default template. Set another as default first."
        )

    db.delete(template)
    db.commit()


# Default email templates
DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Interview Invitation",
        "template_type": "interview_invite",
        "subject": "Interview Request for {position_title} - CrossCountry Freight Solutions",
        "body_html": """<p>Hi {candidate_name},</p>

<p>Thank you for your interest in the <strong>{position_title}</strong> role at CrossCountry Freight Solutions. We've reviewed your application and would like to move forward with the next step in our hiring process.</p>

<p>We use a brief AI-powered interview platform that allows you to share more about your experience and qualifications at a time that's convenient for you. The interview consists of a few questions, and you'll record your responses through the platform. The entire process typically takes 15-20 minutes to complete.</p>

<p><strong>Here's what to do next:</strong></p>
<ul>
<li>Click this link to access your interview: <a href="{interview_url}">{interview_url}</a></li>
<li>Complete the interview within the next {expiry_days} days</li>
<li>You'll need a phone or computer to fill out answers</li>
</ul>

<p>This is a great opportunity to tell us more about yourself and why you're interested in joining our team. Once we review your responses, we'll reach out regarding next steps.</p>

<p>If you need an accommodation to complete or have any technical issues or questions about the process, please don't hesitate to reach out directly.</p>

<p>{recruiter_info}</p>

<p>We appreciate your time and look forward to learning more about you!</p>

<p>Best regards,<br>CrossCountry Freight Solutions Recruiting Team</p>""",
        "body_text": """Hi {candidate_name},

Thank you for your interest in the {position_title} role at CrossCountry Freight Solutions. We've reviewed your application and would like to move forward with the next step in our hiring process.

We use a brief AI-powered interview platform that allows you to share more about your experience and qualifications at a time that's convenient for you. The entire process typically takes 15-20 minutes to complete.

Here's what to do next:
- Click this link to access your interview: {interview_url}
- Complete the interview within the next {expiry_days} days
- You'll need a phone or computer to fill out answers

If you need an accommodation or have any technical issues, please don't hesitate to reach out.

{recruiter_info}

Best regards,
CrossCountry Freight Solutions Recruiting Team""",
    },
    {
        "name": "Interview Reminder",
        "template_type": "reminder",
        "subject": "Reminder: Complete Your Interview for {position_title}",
        "body_html": """<p>Hi {candidate_name},</p>

<p>This is a friendly reminder that your interview for the <strong>{position_title}</strong> position is still waiting for you.</p>

<p>Please complete your interview before it expires: <a href="{interview_url}">{interview_url}</a></p>

<p>The interview only takes about 15-20 minutes to complete.</p>

<p>Best regards,<br>CrossCountry Freight Solutions Recruiting Team</p>""",
        "body_text": """Hi {candidate_name},

This is a friendly reminder that your interview for the {position_title} position is still waiting for you.

Please complete your interview before it expires: {interview_url}

The interview only takes about 15-20 minutes to complete.

Best regards,
CrossCountry Freight Solutions Recruiting Team""",
    },
]


@router.post("/seed")
async def seed_email_templates(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Seed default email templates."""
    seeded = []

    for template_config in DEFAULT_EMAIL_TEMPLATES:
        # Check if template of this type already exists
        existing = db.query(EmailTemplate).filter(
            EmailTemplate.template_type == template_config["template_type"],
            EmailTemplate.is_default == True,
        ).first()

        if existing:
            continue  # Skip if default already exists

        template = EmailTemplate(
            name=template_config["name"],
            template_type=template_config["template_type"],
            subject=template_config["subject"],
            body_html=template_config["body_html"],
            body_text=template_config.get("body_text"),
            is_default=True,
            is_active=True,
        )
        db.add(template)
        seeded.append(template_config["template_type"])

    db.commit()
    return {"message": f"Seeded {len(seeded)} email templates", "types": seeded}
