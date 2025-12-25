"""Email template management endpoints."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.config.database import get_db
from api.models import EmailTemplate
from api.services.rbac import require_role

router = APIRouter()


# Schemas
class EmailTemplateCreate(BaseModel):
    name: str
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    is_active: bool = True
    is_default: bool = False

    class Config:
        from_attributes = True


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

    class Config:
        from_attributes = True


class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: str
    subject: str
    body_html: str
    body_text: Optional[str]
    is_active: bool
    is_default: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class EmailTemplateListResponse(BaseModel):
    data: List[EmailTemplateResponse]
    meta: dict


@router.get("", response_model=EmailTemplateListResponse)
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

    return {
        "data": [
            {
                "id": t.id,
                "name": t.name,
                "template_type": t.template_type,
                "subject": t.subject,
                "body_html": t.body_html,
                "body_text": t.body_text,
                "is_active": t.is_active,
                "is_default": t.is_default,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in templates
        ],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


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

    return {
        "id": template.id,
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


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

    return {
        "id": template.id,
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


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

    return {
        "id": template.id,
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


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
