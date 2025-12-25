"""Activity/logs endpoints."""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import Activity, Application, Requisition
from api.schemas.activities import ActivityListItem
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[ActivityListItem])
async def list_activities(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    application_id: Optional[int] = Query(None),
    requisition_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List activity log entries."""
    query = db.query(Activity)

    # Filters
    if application_id:
        query = query.filter(Activity.application_id == application_id)
    if requisition_id:
        query = query.filter(Activity.requisition_id == requisition_id)
    if action:
        query = query.filter(Activity.action == action)

    # Count total
    total = query.count()

    # Paginate
    activities = query.order_by(Activity.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Get related names
    app_ids = [a.application_id for a in activities if a.application_id]
    req_ids = [a.requisition_id for a in activities if a.requisition_id]

    app_names = dict(
        db.query(Application.id, Application.candidate_name)
        .filter(Application.id.in_(app_ids))
        .all()
    ) if app_ids else {}

    req_names = dict(
        db.query(Requisition.id, Requisition.name)
        .filter(Requisition.id.in_(req_ids))
        .all()
    ) if req_ids else {}

    items = [
        ActivityListItem(
            id=a.id,
            action=a.action,
            application_id=a.application_id,
            candidate_name=app_names.get(a.application_id),
            requisition_name=req_names.get(a.requisition_id),
            details=json.loads(a.details) if a.details else None,
            created_at=a.created_at,
        )
        for a in activities
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
