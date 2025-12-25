"""Requisition CRUD endpoints."""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Requisition, Recruiter, Application, Job
from api.schemas.requisitions import (
    RequisitionCreate,
    RequisitionUpdate,
    RequisitionResponse,
    RequisitionListItem,
    SyncResponse,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[RequisitionListItem])
async def list_requisitions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    recruiter_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all requisitions with pagination."""
    query = db.query(Requisition)

    # Filters
    if search:
        query = query.filter(
            Requisition.name.ilike(f"%{search}%") | Requisition.description.ilike(f"%{search}%")
        )
    if recruiter_id:
        query = query.filter(Requisition.recruiter_id == recruiter_id)
    if is_active is not None:
        query = query.filter(Requisition.is_active == is_active)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Requisition, sort, Requisition.created_at)
    if order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    requisitions = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get application counts
    app_counts = dict(
        db.query(Application.requisition_id, func.count(Application.id))
        .group_by(Application.requisition_id)
        .all()
    )
    pending_counts = dict(
        db.query(Application.requisition_id, func.count(Application.id))
        .filter(Application.status.in_(["new", "analyzing"]))
        .group_by(Application.requisition_id)
        .all()
    )

    # Get recruiter names
    recruiter_ids = [r.recruiter_id for r in requisitions if r.recruiter_id]
    recruiters = {
        r.id: r.name
        for r in db.query(Recruiter).filter(Recruiter.id.in_(recruiter_ids)).all()
    }

    items = [
        RequisitionListItem(
            id=r.id,
            external_id=r.external_id,
            name=r.name,
            location=r.location,
            recruiter_id=r.recruiter_id,
            recruiter_name=recruiters.get(r.recruiter_id),
            is_active=r.is_active,
            auto_send_interview=r.auto_send_interview,
            application_count=app_counts.get(r.id, 0),
            pending_count=pending_counts.get(r.id, 0),
            last_synced_at=r.last_synced_at,
            created_at=r.created_at,
        )
        for r in requisitions
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


@router.get("/{requisition_id}", response_model=RequisitionResponse)
async def get_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a requisition by ID."""
    requisition = db.query(Requisition).filter(Requisition.id == requisition_id).first()
    if not requisition:
        raise NotFoundError("Requisition", requisition_id)

    response = RequisitionResponse(
        id=requisition.id,
        external_id=requisition.external_id,
        name=requisition.name,
        description=requisition.description,
        detailed_description=requisition.detailed_description,
        location=requisition.location,
        recruiter_id=requisition.recruiter_id,
        is_active=requisition.is_active,
        sync_interval_minutes=requisition.sync_interval_minutes,
        lookback_hours=requisition.lookback_hours,
        interview_instructions=requisition.interview_instructions,
        auto_send_interview=requisition.auto_send_interview,
        auto_send_on_status=requisition.auto_send_on_status,
        last_synced_at=requisition.last_synced_at,
        workday_data=json.loads(requisition.workday_data) if requisition.workday_data else None,
        created_at=requisition.created_at,
        updated_at=requisition.updated_at,
    )
    return response


@router.patch("/{requisition_id}", response_model=RequisitionResponse)
async def update_requisition(
    requisition_id: int,
    data: RequisitionUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Update a requisition."""
    requisition = db.query(Requisition).filter(Requisition.id == requisition_id).first()
    if not requisition:
        raise NotFoundError("Requisition", requisition_id)

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(requisition, key, value)

    db.commit()
    db.refresh(requisition)

    logger.info("Requisition updated", id=requisition.id)
    return await get_requisition(requisition_id, db, user)


@router.post("/sync", response_model=SyncResponse)
async def sync_all_requisitions(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Trigger sync for all active requisitions."""
    # Create a sync job without requisition_id - processor will sync all
    job = Job(
        job_type="sync",
        priority=10,  # Higher priority for manual triggers
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Sync all requisitions triggered", job_id=job.id)

    return SyncResponse(
        status="queued",
        queue_item_id=job.id,
        message="Sync job queued for all active requisitions",
    )


@router.post("/{requisition_id}/sync", response_model=SyncResponse)
async def sync_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Trigger manual sync for a specific requisition."""
    requisition = db.query(Requisition).filter(Requisition.id == requisition_id).first()
    if not requisition:
        raise NotFoundError("Requisition", requisition_id)

    # Create a sync job for specific requisition
    job = Job(
        requisition_id=requisition_id,
        job_type="sync",
        priority=10,  # Higher priority for manual triggers
        payload=json.dumps({"requisition_id": requisition_id}),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Sync triggered for requisition", requisition_id=requisition_id, job_id=job.id)

    return SyncResponse(
        status="queued",
        queue_item_id=job.id,
        message=f"Sync job queued for requisition {requisition.external_id}",
    )
