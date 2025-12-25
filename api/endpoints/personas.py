"""Persona CRUD endpoints."""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Persona
from api.schemas.personas import (
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
    PersonaListItem,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[PersonaListItem])
async def list_personas(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_active: bool = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all personas with pagination."""
    query = db.query(Persona)

    if is_active is not None:
        query = query.filter(Persona.is_active == is_active)

    total = query.count()

    personas = query.order_by(Persona.name).offset((page - 1) * per_page).limit(per_page).all()

    items = [
        PersonaListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            is_active=p.is_active,
            is_default=p.is_default,
            created_at=p.created_at,
        )
        for p in personas
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


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a persona by ID."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise NotFoundError("Persona", persona_id)
    return PersonaResponse.model_validate(persona)


@router.post("", response_model=PersonaResponse, status_code=201)
async def create_persona(
    data: PersonaCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Create a new persona."""
    # If setting as default, unset other defaults
    if data.is_default:
        db.query(Persona).filter(Persona.is_default == True).update({"is_default": False})

    persona = Persona(**data.model_dump())
    db.add(persona)
    db.commit()
    db.refresh(persona)

    logger.info("Persona created", id=persona.id, name=persona.name)
    return PersonaResponse.model_validate(persona)


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: int,
    data: PersonaUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update a persona."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise NotFoundError("Persona", persona_id)

    update_data = data.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(Persona).filter(
            Persona.id != persona_id,
            Persona.is_default == True,
        ).update({"is_default": False})

    for key, value in update_data.items():
        setattr(persona, key, value)

    db.commit()
    db.refresh(persona)

    logger.info("Persona updated", id=persona.id)
    return PersonaResponse.model_validate(persona)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Delete a persona (soft delete)."""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise NotFoundError("Persona", persona_id)

    persona.is_active = False
    persona.is_default = False
    db.commit()

    logger.info("Persona deleted (soft)", id=persona.id)
