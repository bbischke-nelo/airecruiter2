"""Application endpoints with Human-in-the-Loop decision actions."""

import json
from datetime import datetime
from typing import Optional, List

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config.database import get_db
from processor.integrations.s3 import S3Service
from api.middleware.error_handler import NotFoundError
from api.models import Application, Requisition, Analysis, Interview, Report, Job, ApplicationDecision, Activity
from api.schemas.applications import (
    ApplicationListItem,
    ApplicationResponse,
    AnalysisResponse,
    ReprocessRequest,
    ReprocessResponse,
    AdvanceRequest,
    RejectRequest,
    HoldRequest,
    DecisionResponse,
    ApplicationDecisionItem,
    ExtractedFactsResponse,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role

logger = structlog.get_logger()
router = APIRouter()

# Valid statuses for human decisions
ADVANCE_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review", "on_hold"}
REJECT_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review", "on_hold", "new", "extracted"}
HOLD_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review"}


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
        # Escape SQL wildcards to prevent unexpected search behavior
        escaped_search = search.replace("%", r"\%").replace("_", r"\_")
        query = query.filter(Application.candidate_name.ilike(f"%{escaped_search}%", escape="\\"))

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

    # Get extracted facts for JD match and tenure
    analyses = (
        db.query(Analysis.application_id, Analysis.extracted_facts)
        .filter(Analysis.application_id.in_(app_ids))
        .all()
    )

    # Parse extracted facts for display fields
    jd_match_percentages = {}
    avg_tenure_months = {}
    for app_id, facts_json in analyses:
        if facts_json:
            try:
                facts = json.loads(facts_json)
                # Calculate JD match percentage
                jd_matches = facts.get("jd_keyword_matches", {})
                found = len(jd_matches.get("found", []))
                not_found = len(jd_matches.get("not_found", []))
                if found + not_found > 0:
                    jd_match_percentages[app_id] = round((found / (found + not_found)) * 100)
                # Get average tenure
                summary = facts.get("summary_stats", {})
                if summary.get("average_tenure_months"):
                    avg_tenure_months[app_id] = summary["average_tenure_months"]
            except (json.JSONDecodeError, TypeError):
                pass

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
            jd_match_percentage=jd_match_percentages.get(a.id),
            avg_tenure_months=avg_tenure_months.get(a.id),
            human_requested=a.human_requested,
            compliance_review=a.compliance_review,
            rejection_reason_code=a.rejection_reason_code,
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

    # Safely parse artifacts JSON
    try:
        artifacts = json.loads(application.artifacts) if application.artifacts else {}
    except (json.JSONDecodeError, TypeError):
        artifacts = {}

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
        artifacts=artifacts,
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

    # Safely parse JSON fields
    def safe_json_loads(data, default=None):
        if not data:
            return default if default is not None else []
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []

    return AnalysisResponse(
        id=analysis.id,
        application_id=analysis.application_id,
        extraction_version=analysis.extraction_version,
        extraction_notes=analysis.extraction_notes,
        extracted_facts=safe_json_loads(analysis.extracted_facts, {}),
        relevance_summary=analysis.relevance_summary,
        pros=safe_json_loads(analysis.pros),
        cons=safe_json_loads(analysis.cons),
        suggested_questions=safe_json_loads(analysis.suggested_questions),
        compliance_flags=safe_json_loads(analysis.compliance_flags),
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


# Human-in-the-Loop Decision Endpoints

@router.post("/{application_id}/advance", response_model=DecisionResponse)
async def advance_application(
    application_id: int,
    data: AdvanceRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Advance an application to the next stage.

    Valid from: ready_for_review, interview_ready_for_review, on_hold
    """
    # Use row locking to prevent race conditions from double-clicks
    application = db.query(Application).filter(Application.id == application_id).with_for_update().first()
    if not application:
        raise NotFoundError("Application", application_id)

    if application.status not in ADVANCE_VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot advance application with status '{application.status}'. Valid statuses: {ADVANCE_VALID_STATUSES}",
        )

    from_status = application.status

    # Determine next status based on current status and config
    if application.status == "ready_for_review":
        if data.skip_interview:
            to_status = "live_interview_pending"
        else:
            # Queue interview send job
            to_status = "advancing"
            job = Job(
                application_id=application_id,
                job_type="send_interview",
                priority=5,
            )
            db.add(job)
    elif application.status == "interview_ready_for_review":
        to_status = "advanced"
    elif application.status == "on_hold":
        # Restore to previous status or ready_for_review
        to_status = "ready_for_review"
    else:
        to_status = "advanced"

    # Update application
    application.status = to_status
    application.advanced_by = user.get("id")
    application.advanced_at = datetime.utcnow()

    # Log decision
    decision = ApplicationDecision(
        application_id=application_id,
        action="advance",
        from_status=from_status,
        to_status=to_status,
        comment=data.notes,
        user_id=user.get("id", 0),
    )
    db.add(decision)

    # Log activity
    activity = Activity(
        action="application_advanced",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "from_status": from_status,
            "to_status": to_status,
            "skip_interview": data.skip_interview,
        }),
    )
    db.add(activity)

    db.commit()

    logger.info(
        "Application advanced",
        application_id=application_id,
        from_status=from_status,
        to_status=to_status,
        user_id=user.get("id"),
    )

    return DecisionResponse(
        success=True,
        application_id=application_id,
        action="advance",
        from_status=from_status,
        to_status=to_status,
        message=f"Application advanced from {from_status} to {to_status}",
    )


@router.post("/{application_id}/reject", response_model=DecisionResponse)
async def reject_application(
    application_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Reject an application with a legally defensible reason code.

    Note: No free-form comments allowed - they become discovery liabilities.
    """
    # Use row locking to prevent race conditions from double-clicks
    application = db.query(Application).filter(Application.id == application_id).with_for_update().first()
    if not application:
        raise NotFoundError("Application", application_id)

    if application.status not in REJECT_VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject application with status '{application.status}'. Valid statuses: {REJECT_VALID_STATUSES}",
        )

    from_status = application.status
    to_status = "rejected"

    # Update application
    application.status = to_status
    application.rejection_reason_code = data.reason_code.value
    application.rejected_by = user.get("id")
    application.rejected_at = datetime.utcnow()

    # Log decision (no comment stored - discovery liability)
    decision = ApplicationDecision(
        application_id=application_id,
        action="reject",
        from_status=from_status,
        to_status=to_status,
        reason_code=data.reason_code.value,
        user_id=user.get("id", 0),
    )
    db.add(decision)

    # Log activity
    activity = Activity(
        action="application_rejected",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "from_status": from_status,
            "reason_code": data.reason_code.value,
        }),
    )
    db.add(activity)

    db.commit()

    logger.info(
        "Application rejected",
        application_id=application_id,
        reason_code=data.reason_code.value,
        user_id=user.get("id"),
    )

    return DecisionResponse(
        success=True,
        application_id=application_id,
        action="reject",
        from_status=from_status,
        to_status=to_status,
        message=f"Application rejected with reason: {data.reason_code.value}",
    )


@router.post("/{application_id}/hold", response_model=DecisionResponse)
async def hold_application(
    application_id: int,
    data: HoldRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Put an application on hold.

    Note: No free-form reason accepted - discovery liability.
    """
    # Use row locking to prevent race conditions from double-clicks
    application = db.query(Application).filter(Application.id == application_id).with_for_update().first()
    if not application:
        raise NotFoundError("Application", application_id)

    if application.status not in HOLD_VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot hold application with status '{application.status}'. Valid statuses: {HOLD_VALID_STATUSES}",
        )

    from_status = application.status
    to_status = "on_hold"

    # Update application
    application.status = to_status

    # Log decision (no free-form reason - discovery liability)
    decision = ApplicationDecision(
        application_id=application_id,
        action="hold",
        from_status=from_status,
        to_status=to_status,
        user_id=user.get("id", 0),
    )
    db.add(decision)

    # Log activity
    activity = Activity(
        action="application_held",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "from_status": from_status,
        }),
    )
    db.add(activity)

    db.commit()

    logger.info(
        "Application held",
        application_id=application_id,
        from_status=from_status,
        user_id=user.get("id"),
    )

    return DecisionResponse(
        success=True,
        application_id=application_id,
        action="hold",
        from_status=from_status,
        to_status=to_status,
        message="Application placed on hold",
    )


@router.get("/{application_id}/decisions", response_model=List[ApplicationDecisionItem])
async def get_application_decisions(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get decision audit trail for an application."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    decisions = (
        db.query(ApplicationDecision)
        .filter(ApplicationDecision.application_id == application_id)
        .order_by(ApplicationDecision.created_at.desc())
        .all()
    )

    return [
        ApplicationDecisionItem(
            id=d.id,
            application_id=d.application_id,
            action=d.action,
            from_status=d.from_status,
            to_status=d.to_status,
            reason_code=d.reason_code,
            comment=d.comment,
            user_id=d.user_id,
            created_at=d.created_at,
        )
        for d in decisions
    ]


@router.get("/{application_id}/facts", response_model=ExtractedFactsResponse)
async def get_application_facts(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get extracted facts for an application."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    analysis = db.query(Analysis).filter(Analysis.application_id == application_id).first()
    if not analysis:
        raise NotFoundError("Analysis", application_id)

    # Safely parse JSON fields
    def safe_json_loads(data, default=None):
        if not data:
            return default if default is not None else []
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []

    return ExtractedFactsResponse(
        id=analysis.id,
        application_id=analysis.application_id,
        extraction_version=analysis.extraction_version,
        extraction_notes=analysis.extraction_notes,
        extracted_facts=safe_json_loads(analysis.extracted_facts, None),
        relevance_summary=analysis.relevance_summary,
        pros=safe_json_loads(analysis.pros),
        cons=safe_json_loads(analysis.cons),
        suggested_questions=safe_json_loads(analysis.suggested_questions),
        model_version=analysis.model_version,
        created_at=analysis.created_at,
    )


# Download endpoints

class DownloadUrlResponse(BaseModel):
    url: str
    filename: str


@router.get("/{application_id}/resume/download", response_model=DownloadUrlResponse)
async def get_resume_download_url(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get presigned URL to download the resume."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Parse artifacts to get resume key
    try:
        artifacts = json.loads(application.artifacts) if application.artifacts else {}
    except (json.JSONDecodeError, TypeError):
        artifacts = {}

    resume_key = artifacts.get("resume")
    if not resume_key:
        raise HTTPException(status_code=404, detail="No resume available for this application")

    filename = artifacts.get("resume_filename", "resume.pdf")

    # Generate presigned URL
    s3 = S3Service()
    url = await s3.get_presigned_url(resume_key, expires_in=3600)

    return DownloadUrlResponse(url=url, filename=filename)


@router.get("/{application_id}/report/download", response_model=DownloadUrlResponse)
async def get_report_download_url(
    application_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get presigned URL to download the analysis report."""
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Get the report
    report = db.query(Report).filter(Report.application_id == application_id).order_by(Report.created_at.desc()).first()
    if not report or not report.s3_key:
        raise HTTPException(status_code=404, detail="No report available for this application")

    # Generate filename
    safe_name = "".join(c for c in application.candidate_name if c.isalnum() or c in " -_").strip()
    filename = f"Candidate_Summary_{safe_name}.pdf"

    # Generate presigned URL
    s3 = S3Service()
    url = await s3.get_presigned_url(report.s3_key, expires_in=3600)

    return DownloadUrlResponse(url=url, filename=filename)
