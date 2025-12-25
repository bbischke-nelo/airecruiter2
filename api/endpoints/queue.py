"""Queue management endpoints."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Job, Application, Requisition
from api.schemas.queue import (
    QueueItem,
    QueueStatusResponse,
    QueueAddRequest,
    QueueAddResponse,
)
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=QueueStatusResponse)
async def get_queue_status(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get queue status with item counts and recent items."""
    # Get counts by status
    counts = dict(
        db.query(Job.status, func.count(Job.id))
        .group_by(Job.status)
        .all()
    )

    # Get recent items
    query = db.query(Job).join(Application).join(Requisition)
    if status_filter:
        query = query.filter(Job.status == status_filter)
    else:
        query = query.filter(Job.status.in_(["pending", "running", "failed"]))

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

    items = [
        QueueItem(
            id=j.id,
            job_type=j.job_type,
            application_id=j.application_id,
            requisition_name=j.application.requisition.name if j.application else None,
            candidate_name=j.application.candidate_name if j.application else None,
            status=j.status,
            priority=j.priority,
            attempts=j.attempts,
            max_attempts=j.max_attempts,
            last_error=j.last_error,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            scheduled_for=j.scheduled_for,
        )
        for j in jobs
    ]

    return QueueStatusResponse(
        pending=counts.get("pending", 0),
        running=counts.get("running", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        dead=counts.get("dead", 0),
        items=items,
    )


@router.post("", response_model=QueueAddResponse, status_code=201)
async def add_to_queue(
    data: QueueAddRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Manually add a job to the queue."""
    job = Job(
        application_id=data.application_id or 0,
        job_type=data.job_type,
        priority=data.priority,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Job added manually", job_id=job.id, job_type=job.job_type)

    return QueueAddResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
    )


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Retry a failed job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundError("Job", job_id)

    if job.status not in ["failed", "dead"]:
        return {"message": f"Job is {job.status}, not failed"}

    job.status = "pending"
    job.attempts = 0
    job.last_error = None
    job.started_at = None
    job.completed_at = None
    db.commit()

    logger.info("Job retry triggered", job_id=job_id)
    return {"message": "Job queued for retry"}


@router.delete("/completed", status_code=204)
async def clear_completed(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Clear all completed jobs from queue."""
    count = db.query(Job).filter(Job.status == "completed").delete()
    db.commit()

    logger.info("Cleared completed jobs", count=count)


@router.delete("", status_code=204)
async def clear_all(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Clear entire queue (dangerous!)."""
    count = db.query(Job).delete()
    db.commit()

    logger.warning("Cleared all jobs", count=count)
