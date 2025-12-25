"""Application endpoints (read-only + reprocess)."""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Application, Requisition, Analysis, Interview, Report, Job
from api.schemas.applications import (
    ApplicationListItem,
    ApplicationResponse,
    AnalysisResponse,
    ReprocessRequest,
    ReprocessResponse,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[ApplicationListItem])
async def list_applications(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    requisition_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all applications with pagination."""
    query = db.query(Application).join(Requisition)

    # Filters
    if requisition_id:
        query = query.filter(Application.requisition_id == requisition_id)
    if status:
        query = query.filter(Application.status == status)
    if search:
        query = query.filter(Application.candidate_name.ilike(f"%{search}%"))

    # Count total
    total = query.count()

    # Paginate
    applications = query.order_by(Application.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Get related data
    app_ids = [a.id for a in applications]

    # Check for analysis
    analysis_app_ids = set(
        row[0]
        for row in db.query(Analysis.application_id)
        .filter(Analysis.application_id.in_(app_ids))
        .all()
    )

    # Check for interviews
    interview_app_ids = set(
        row[0]
        for row in db.query(Interview.application_id)
        .filter(Interview.application_id.in_(app_ids))
        .all()
    )

    # Check for reports
    report_app_ids = set(
        row[0]
        for row in db.query(Report.application_id)
        .filter(Report.application_id.in_(app_ids))
        .all()
    )

    # Get risk scores
    risk_scores = dict(
        db.query(Analysis.application_id, Analysis.risk_score)
        .filter(Analysis.application_id.in_(app_ids))
        .all()
    )

    items = [
        ApplicationListItem(
            id=a.id,
            requisition_id=a.requisition_id,
            requisition_name=a.requisition.name,
            external_application_id=a.external_application_id,
            candidate_name=a.candidate_name,
            candidate_email=a.candidate_email,
            status=a.status,
            workday_status=a.workday_status,
            has_analysis=a.id in analysis_app_ids,
            has_interview=a.id in interview_app_ids,
            has_report=a.id in report_app_ids,
            risk_score=risk_scores.get(a.id),
            human_requested=a.human_requested,
            compliance_review=a.compliance_review,
            created_at=a.created_at,
        )
        for a in applications
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


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get an application by ID."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    return ApplicationResponse(
        id=application.id,
        requisition_id=application.requisition_id,
        external_application_id=application.external_application_id,
        external_candidate_id=application.external_candidate_id,
        candidate_name=application.candidate_name,
        candidate_email=application.candidate_email,
        status=application.status,
        workday_status=application.workday_status,
        workday_status_changed=application.workday_status_changed,
        human_requested=application.human_requested,
        compliance_review=application.compliance_review,
        artifacts=json.loads(application.artifacts) if application.artifacts else {},
        created_at=application.created_at,
        updated_at=application.updated_at,
        processed_at=application.processed_at,
    )


@router.get("/{application_id}/analysis", response_model=AnalysisResponse)
async def get_application_analysis(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get analysis for an application."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    analysis = db.query(Analysis).filter(Analysis.application_id == application_id).first()
    if not analysis:
        raise NotFoundError("Analysis", application_id)

    return AnalysisResponse(
        id=analysis.id,
        application_id=analysis.application_id,
        risk_score=analysis.risk_score,
        relevance_summary=analysis.relevance_summary,
        pros=json.loads(analysis.pros) if analysis.pros else [],
        cons=json.loads(analysis.cons) if analysis.cons else [],
        red_flags=json.loads(analysis.red_flags) if analysis.red_flags else [],
        suggested_questions=json.loads(analysis.suggested_questions) if analysis.suggested_questions else [],
        compliance_flags=json.loads(analysis.compliance_flags) if analysis.compliance_flags else [],
        model_version=analysis.model_version,
        created_at=analysis.created_at,
    )


@router.post("/{application_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_application(
    application_id: int,
    data: ReprocessRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Reprocess an application from a specific step."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Map step to job type
    step_to_job = {
        "analyze": "analyze",
        "send_interview": "send_interview",
        "evaluate": "evaluate",
        "generate_report": "generate_report",
    }

    job_type = step_to_job.get(data.from_step, "analyze")

    # Create job
    job = Job(
        application_id=application_id,
        job_type=job_type,
        priority=5,  # Medium priority for reprocess
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(
        "Reprocess triggered",
        application_id=application_id,
        from_step=data.from_step,
        job_id=job.id,
    )

    return ReprocessResponse(
        status="queued",
        queue_item_id=job.id,
        message=f"Reprocess job queued from step '{data.from_step}'",
    )
