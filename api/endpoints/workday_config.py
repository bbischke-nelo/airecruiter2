"""Rejection reasons endpoints for recruiter dropdown."""

from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import RejectionReason, DEFAULT_REJECTION_REASONS
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


# Schemas
class RejectionReasonResponse(BaseModel):
    """Response schema for rejection reason."""

    id: int
    code: str
    external_id: str
    name: str
    requires_comment: bool
    sort_order: int
    is_active: bool

    class Config:
        from_attributes = True


class RejectionReasonCreate(BaseModel):
    """Create schema for rejection reason."""

    code: str
    external_id: str
    name: str
    requires_comment: bool = False
    sort_order: int = 0
    is_active: bool = True


class RejectionReasonUpdate(BaseModel):
    """Update schema for rejection reason."""

    code: str | None = None
    external_id: str | None = None
    name: str | None = None
    requires_comment: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# Rejection Reasons Endpoints
@router.get("/rejection-reasons", response_model=List[RejectionReasonResponse])
async def list_rejection_reasons(
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all rejection reasons."""
    query = db.query(RejectionReason)
    if active_only:
        query = query.filter(RejectionReason.is_active == True)
    reasons = query.order_by(RejectionReason.sort_order).all()
    return reasons


@router.get("/rejection-reasons/{reason_id}", response_model=RejectionReasonResponse)
async def get_rejection_reason(
    reason_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get a specific rejection reason."""
    reason = db.query(RejectionReason).filter(RejectionReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail="Rejection reason not found")
    return reason


@router.post("/rejection-reasons", response_model=RejectionReasonResponse)
async def create_rejection_reason(
    data: RejectionReasonCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Create a new rejection reason."""
    # Check for duplicate code
    existing = db.query(RejectionReason).filter(RejectionReason.code == data.code).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Rejection reason with code '{data.code}' already exists",
        )

    reason = RejectionReason(**data.model_dump())
    db.add(reason)
    db.commit()
    db.refresh(reason)

    logger.info("Rejection reason created", reason_id=reason.id, code=reason.code)
    return reason


@router.patch("/rejection-reasons/{reason_id}", response_model=RejectionReasonResponse)
async def update_rejection_reason(
    reason_id: int,
    data: RejectionReasonUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update a rejection reason."""
    reason = db.query(RejectionReason).filter(RejectionReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail="Rejection reason not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(reason, key, value)

    db.commit()
    db.refresh(reason)

    logger.info("Rejection reason updated", reason_id=reason_id)
    return reason


@router.delete("/rejection-reasons/{reason_id}")
async def delete_rejection_reason(
    reason_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Delete a rejection reason (soft delete - sets is_active=False)."""
    reason = db.query(RejectionReason).filter(RejectionReason.id == reason_id).first()
    if not reason:
        raise HTTPException(status_code=404, detail="Rejection reason not found")

    reason.is_active = False
    db.commit()

    logger.info("Rejection reason deactivated", reason_id=reason_id)
    return {"message": "Rejection reason deactivated"}


@router.post("/rejection-reasons/seed")
async def seed_rejection_reasons(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Seed default rejection reasons if not present."""
    created = 0
    for reason_data in DEFAULT_REJECTION_REASONS:
        existing = db.query(RejectionReason).filter(
            RejectionReason.code == reason_data["code"]
        ).first()
        if not existing:
            reason = RejectionReason(**reason_data)
            db.add(reason)
            created += 1

    db.commit()
    logger.info("Rejection reasons seeded", created=created)
    return {"message": f"Seeded {created} rejection reasons"}
