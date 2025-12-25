"""Report template management endpoints."""

from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.config.database import get_db
from api.models import ReportTemplate
from api.services.rbac import require_role

router = APIRouter()


# Schemas
class ReportTemplateCreate(BaseModel):
    name: str
    template_type: str
    body_html: str
    custom_css: Optional[str] = None
    is_active: bool = True
    is_default: bool = False

    class Config:
        from_attributes = True


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    body_html: Optional[str] = None
    custom_css: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

    class Config:
        from_attributes = True


class ReportTemplateResponse(BaseModel):
    id: int
    name: str
    template_type: str
    body_html: str
    custom_css: Optional[str]
    is_active: bool
    is_default: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class ReportTemplateListResponse(BaseModel):
    data: List[ReportTemplateResponse]
    meta: dict


@router.get("", response_model=ReportTemplateListResponse)
async def list_report_templates(
    template_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all report templates with optional filtering."""
    query = db.query(ReportTemplate)

    if template_type:
        query = query.filter(ReportTemplate.template_type == template_type)
    if is_active is not None:
        query = query.filter(ReportTemplate.is_active == is_active)

    total = query.count()
    templates = (
        query.order_by(ReportTemplate.template_type, ReportTemplate.name)
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
                "body_html": t.body_html,
                "custom_css": t.custom_css,
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


@router.get("/{template_id}", response_model=ReportTemplateResponse)
async def get_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a specific report template."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": template.id,
        "name": template.name,
        "template_type": template.template_type,
        "body_html": template.body_html,
        "custom_css": template.custom_css,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


@router.post("", response_model=ReportTemplateResponse, status_code=201)
async def create_report_template(
    data: ReportTemplateCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Create a new report template."""
    # If setting as default, unset other defaults of same type
    if data.is_default:
        db.query(ReportTemplate).filter(
            ReportTemplate.template_type == data.template_type,
            ReportTemplate.is_default == True,
        ).update({"is_default": False})

    template = ReportTemplate(
        name=data.name,
        template_type=data.template_type,
        body_html=data.body_html,
        custom_css=data.custom_css,
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
        "body_html": template.body_html,
        "custom_css": template.custom_css,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


@router.patch("/{template_id}", response_model=ReportTemplateResponse)
async def update_report_template(
    template_id: int,
    data: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Update a report template."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If setting as default, unset other defaults of same type
    if data.is_default:
        template_type = data.template_type or template.template_type
        db.query(ReportTemplate).filter(
            ReportTemplate.template_type == template_type,
            ReportTemplate.is_default == True,
            ReportTemplate.id != template_id,
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
        "body_html": template.body_html,
        "custom_css": template.custom_css,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


@router.delete("/{template_id}", status_code=204)
async def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Delete a report template."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default template. Set another as default first."
        )

    db.delete(template)
    db.commit()


@router.post("/seed")
async def seed_report_templates(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Seed default report templates from config files."""
    templates_dir = Path(__file__).parent.parent / "config" / "templates"
    seeded = []

    default_templates = [
        {
            "name": "Analysis Report",
            "template_type": "analysis",
            "file": "analysis.html",
        },
        {
            "name": "Interview Report",
            "template_type": "interview_report",
            "file": "interview_report.html",
        },
    ]

    for template_config in default_templates:
        # Check if template of this type already exists
        existing = db.query(ReportTemplate).filter(
            ReportTemplate.template_type == template_config["template_type"],
            ReportTemplate.is_default == True,
        ).first()

        if existing:
            continue  # Skip if default already exists

        # Read template content from file
        template_path = templates_dir / template_config["file"]
        if not template_path.exists():
            continue

        body_html = template_path.read_text()

        template = ReportTemplate(
            name=template_config["name"],
            template_type=template_config["template_type"],
            body_html=body_html,
            is_default=True,
            is_active=True,
        )
        db.add(template)
        seeded.append(template_config["template_type"])

    db.commit()
    return {"message": f"Seeded {len(seeded)} report templates", "types": seeded}
