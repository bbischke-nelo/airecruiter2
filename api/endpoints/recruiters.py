"""Recruiter CRUD endpoints."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Recruiter, Requisition
from api.schemas.recruiters import (
    RecruiterCreate,
    RecruiterUpdate,
    RecruiterResponse,
    RecruiterListItem,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[RecruiterListItem])
async def list_recruiters(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all recruiters with pagination."""
    query = db.query(Recruiter)

    # Filters
    if search:
        query = query.filter(Recruiter.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(Recruiter.is_active == is_active)

    # Count total
    total = query.count()

    # Paginate
    recruiters = query.order_by(Recruiter.name).offset((page - 1) * per_page).limit(per_page).all()

    # Get requisition counts
    req_counts = dict(
        db.query(Requisition.recruiter_id, func.count(Requisition.id))
        .group_by(Requisition.recruiter_id)
        .all()
    )

    items = [
        RecruiterListItem(
            id=r.id,
            name=r.name,
            email=r.email,
            title=r.title,
            is_active=r.is_active,
            requisition_count=req_counts.get(r.id, 0),
        )
        for r in recruiters
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


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a recruiter by ID."""
    recruiter = db.query(Recruiter).filter(Recruiter.id == recruiter_id).first()
    if not recruiter:
        raise NotFoundError("Recruiter", recruiter_id)
    return RecruiterResponse.model_validate(recruiter)


@router.post("", response_model=RecruiterResponse, status_code=201)
async def create_recruiter(
    data: RecruiterCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Create a new recruiter."""
    recruiter = Recruiter(**data.model_dump())
    db.add(recruiter)
    db.commit()
    db.refresh(recruiter)

    logger.info("Recruiter created", id=recruiter.id, name=recruiter.name)
    return RecruiterResponse.model_validate(recruiter)


@router.patch("/{recruiter_id}", response_model=RecruiterResponse)
async def update_recruiter(
    recruiter_id: int,
    data: RecruiterUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update a recruiter."""
    recruiter = db.query(Recruiter).filter(Recruiter.id == recruiter_id).first()
    if not recruiter:
        raise NotFoundError("Recruiter", recruiter_id)

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(recruiter, key, value)

    db.commit()
    db.refresh(recruiter)

    logger.info("Recruiter updated", id=recruiter.id)
    return RecruiterResponse.model_validate(recruiter)


@router.delete("/{recruiter_id}", status_code=204)
async def delete_recruiter(
    recruiter_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Soft delete a recruiter (set inactive)."""
    recruiter = db.query(Recruiter).filter(Recruiter.id == recruiter_id).first()
    if not recruiter:
        raise NotFoundError("Recruiter", recruiter_id)

    recruiter.is_active = False
    db.commit()

    logger.info("Recruiter deleted (soft)", id=recruiter.id)
