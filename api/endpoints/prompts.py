"""Prompt CRUD endpoints."""

from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Prompt
from api.schemas.prompts import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptListItem,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[PromptListItem])
async def list_prompts(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    prompt_type: Optional[str] = Query(None),
    requisition_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all prompts with pagination."""
    query = db.query(Prompt)

    # Filters
    if prompt_type:
        query = query.filter(Prompt.prompt_type == prompt_type)
    if requisition_id:
        query = query.filter(Prompt.requisition_id == requisition_id)
    if is_active is not None:
        query = query.filter(Prompt.is_active == is_active)

    # Count total
    total = query.count()

    # Paginate
    prompts = query.order_by(Prompt.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    items = [
        PromptListItem(
            id=p.id,
            name=p.name,
            prompt_type=p.prompt_type,
            requisition_id=p.requisition_id,
            is_active=p.is_active,
            is_default=p.is_default,
            version=p.version,
            created_at=p.created_at,
        )
        for p in prompts
    ]

    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a prompt by ID."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise NotFoundError("Prompt", prompt_id)
    return PromptResponse.model_validate(prompt)


@router.post("", response_model=PromptResponse, status_code=201)
async def create_prompt(
    data: PromptCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Create a new prompt."""
    # If setting as default, unset other defaults of same type
    if data.is_default:
        db.query(Prompt).filter(
            Prompt.prompt_type == data.prompt_type,
            Prompt.requisition_id == data.requisition_id,
            Prompt.is_default == True,
        ).update({"is_default": False})

    prompt = Prompt(
        **data.model_dump(),
        created_by=user.get("email"),
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    logger.info("Prompt created", id=prompt.id, name=prompt.name)
    return PromptResponse.model_validate(prompt)


@router.patch("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update a prompt."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise NotFoundError("Prompt", prompt_id)

    update_data = data.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(Prompt).filter(
            Prompt.prompt_type == prompt.prompt_type,
            Prompt.requisition_id == prompt.requisition_id,
            Prompt.id != prompt_id,
            Prompt.is_default == True,
        ).update({"is_default": False})

    # Increment version if content changed
    if "template_content" in update_data or "schema_content" in update_data:
        prompt.version = prompt.version + 1

    for key, value in update_data.items():
        setattr(prompt, key, value)

    prompt.updated_by = user.get("email")
    db.commit()
    db.refresh(prompt)

    logger.info("Prompt updated", id=prompt.id)
    return PromptResponse.model_validate(prompt)


@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Delete a prompt (soft delete - set inactive)."""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise NotFoundError("Prompt", prompt_id)

    prompt.is_active = False
    prompt.is_default = False
    db.commit()

    logger.info("Prompt deleted (soft)", id=prompt.id)


# Default prompts to seed from config files
DEFAULT_PROMPTS = [
    {
        "name": "Resume Analysis",
        "prompt_type": "resume_analysis",
        "description": "Analyzes resumes for retention, safety, and role fit",
        "file": "resume_analysis.md",
        "schema_file": "resume_analysis_example.json",
    },
    {
        "name": "Interview",
        "prompt_type": "interview",
        "description": "Admin-initiated interview prompt",
        "file": "interview.md",
    },
    {
        "name": "Self-Service Interview",
        "prompt_type": "self_service_interview",
        "description": "Candidate-facing interview prompt",
        "file": "self_service_interview.md",
    },
    {
        "name": "Evaluation",
        "prompt_type": "evaluation",
        "description": "Post-interview evaluation prompt",
        "file": "evaluation.md",
    },
    {
        "name": "Interview Email",
        "prompt_type": "interview_email",
        "description": "Interview invitation email template",
        "file": "interview_email.md",
    },
]


@router.post("/seed")
async def seed_prompts(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Seed default prompts from config files."""
    prompts_dir = Path(__file__).parent.parent / "config" / "prompts"
    seeded = []

    for prompt_config in DEFAULT_PROMPTS:
        # Check if prompt of this type already exists
        existing = db.query(Prompt).filter(
            Prompt.prompt_type == prompt_config["prompt_type"],
            Prompt.requisition_id == None,
            Prompt.is_default == True,
        ).first()

        if existing:
            continue  # Skip if default already exists

        # Read template content from file
        template_path = prompts_dir / prompt_config["file"]
        if not template_path.exists():
            logger.warning("Prompt template not found", path=str(template_path))
            continue

        template_content = template_path.read_text()

        # Read schema content if specified
        schema_content = None
        if "schema_file" in prompt_config:
            schema_path = prompts_dir / prompt_config["schema_file"]
            if schema_path.exists():
                schema_content = schema_path.read_text()

        # Create prompt
        prompt = Prompt(
            name=prompt_config["name"],
            prompt_type=prompt_config["prompt_type"],
            template_content=template_content,
            schema_content=schema_content,
            description=prompt_config.get("description"),
            is_default=True,
            is_active=True,
            created_by="system",
        )
        db.add(prompt)
        seeded.append(prompt_config["prompt_type"])

    db.commit()
    logger.info("Prompts seeded", types=seeded)
    return {"message": f"Seeded {len(seeded)} prompts", "types": seeded}
