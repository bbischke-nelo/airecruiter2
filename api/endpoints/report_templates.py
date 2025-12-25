"""Report template management endpoints."""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import ReportTemplate
from api.schemas.base import CamelModel, PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()


# Schemas
class ReportTemplateCreate(CamelModel):
    name: str
    template_type: str
    body_html: str
    custom_css: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class ReportTemplateUpdate(CamelModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    body_html: Optional[str] = None
    custom_css: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ReportTemplateResponse(CamelModel):
    id: int
    name: str
    template_type: str
    body_html: str
    custom_css: Optional[str]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime]


@router.get("", response_model=PaginatedResponse[ReportTemplateResponse])
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

    items = [ReportTemplateResponse.model_validate(t) for t in templates]

    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


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

    return ReportTemplateResponse.model_validate(template)


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

    logger.info("Report template created", id=template.id, name=template.name)
    return ReportTemplateResponse.model_validate(template)


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

    logger.info("Report template updated", id=template.id)
    return ReportTemplateResponse.model_validate(template)


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
    logger.info("Report template deleted", id=template_id)


@router.post("/seed")
async def seed_report_templates(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin"])),
):
    """Seed default report templates from config files."""
    templates_dir = Path(__file__).parent.parent / "config" / "templates"
    logger.info("Seeding report templates", templates_dir=str(templates_dir))
    seeded = []
    skipped = []

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
            skipped.append(f"{template_config['template_type']} (already exists)")
            continue

        # Read template content from file
        template_path = templates_dir / template_config["file"]
        if not template_path.exists():
            skipped.append(f"{template_config['template_type']} (file not found: {template_config['file']})")
            logger.warning("Template file not found", path=str(template_path))
            continue

        body_html = template_path.read_text()
        logger.info("Loading template", type=template_config["template_type"], size=len(body_html))

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
    logger.info("Report templates seeded", seeded=seeded, skipped=skipped)
    return {
        "message": f"Seeded {len(seeded)} report templates",
        "seeded": seeded,
        "skipped": skipped,
    }
