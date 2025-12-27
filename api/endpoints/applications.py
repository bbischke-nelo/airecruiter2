"""Application endpoints with Human-in-the-Loop decision actions."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.config.settings import settings
from api.services.s3 import S3Service
from api.middleware.error_handler import NotFoundError
from api.models import Application, Requisition, Analysis, Interview, Report, Job, ApplicationDecision, Activity, Setting, RejectionReason, Message
from api.schemas.applications import (
    ApplicationListItem,
    ApplicationResponse,
    AnalysisResponse,
    ReprocessRequest,
    ReprocessResponse,
    AdvanceRequest,
    RejectRequest,
    HoldRequest,
    UnrejectRequest,
    DecisionResponse,
    ApplicationDecisionItem,
    ExtractedFactsResponse,
)
from api.schemas.interviews import (
    PrepareInterviewRequest,
    PrepareInterviewResponse,
    ActivateInterviewRequest,
    ActivateInterviewResponse,
    StartProxyInterviewRequest,
    StartProxyInterviewResponse,
    MessageResponse,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role
from api.services.email_preview import generate_interview_email_preview
from api.services.interview_service import InterviewService

logger = structlog.get_logger()
router = APIRouter()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Get a setting value from the database."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else default

# Valid statuses for human decisions
ADVANCE_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review", "on_hold"}
REJECT_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review", "on_hold", "new", "extracted"}
HOLD_VALID_STATUSES = {"ready_for_review", "interview_ready_for_review"}


# Valid sort columns for server-side sorting
SORTABLE_COLUMNS = {
    "candidateName": Application.candidate_name,
    "status": Application.status,
    "createdAt": Application.created_at,
    "requisitionName": Requisition.name,
    # Denormalized sort columns from extract_facts
    "jdMatchPercentage": Application.jd_match_percentage,
    "totalExperienceMonths": Application.total_experience_months,
    "avgTenureMonths": Application.avg_tenure_months,
    "currentTitle": Application.current_title,
}


@router.get("", response_model=PaginatedResponse[ApplicationListItem])
async def list_applications(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    requisition_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    exclude_statuses: Optional[str] = Query(None, description="Comma-separated statuses to exclude"),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, description="Column to sort by"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order: asc or desc"),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all applications with pagination and server-side sorting."""
    query = db.query(Application).join(Requisition)

    # Filters
    if requisition_id:
        query = query.filter(Application.requisition_id == requisition_id)
    if status:
        query = query.filter(Application.status == status)
    if exclude_statuses:
        excluded = [s.strip() for s in exclude_statuses.split(",") if s.strip()]
        if excluded:
            query = query.filter(~Application.status.in_(excluded))
    if search:
        # Escape SQL wildcards to prevent unexpected search behavior
        escaped_search = search.replace("%", r"\%").replace("_", r"\_")
        query = query.filter(Application.candidate_name.ilike(f"%{escaped_search}%", escape="\\"))

    # Count total
    total = query.count()

    # Server-side sorting
    if sort_by and sort_by in SORTABLE_COLUMNS:
        sort_column = SORTABLE_COLUMNS[sort_by]
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
    else:
        # Default sort: newest first
        query = query.order_by(Application.created_at.desc())

    # Paginate
    applications = query.offset((page - 1) * per_page).limit(per_page).all()

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

    # Note: Sort columns (jd_match_percentage, total_experience_months, avg_tenure_months,
    # current_title, current_employer, months_since_last_employment) are now denormalized
    # directly on the applications table for efficient sorting. No JSON parsing needed.

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
            # Denormalized sort columns (populated by extract_facts processor)
            jd_match_percentage=a.jd_match_percentage,
            avg_tenure_months=a.avg_tenure_months,
            current_title=a.current_title,
            current_employer=a.current_employer,
            total_experience_months=a.total_experience_months,
            months_since_last_employment=a.months_since_last_employment,
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
    tms_stage_key = None  # Setting key to look up TMS stage ID

    # Determine next status based on current status and config
    if application.status == "ready_for_review":
        if data.skip_interview:
            to_status = "live_interview_pending"
            tms_stage_key = "tms_status_live_interview"
        else:
            # Queue interview send job
            to_status = "advancing"
            tms_stage_key = "tms_status_ai_interview"
            job = Job(
                application_id=application_id,
                job_type="send_interview",
                priority=5,
            )
            db.add(job)
    elif application.status == "interview_ready_for_review":
        to_status = "advanced"
        tms_stage_key = "tms_status_advanced"
    elif application.status == "on_hold":
        # Restore to previous status or ready_for_review
        to_status = "ready_for_review"
        # No TMS sync for unhold - they stay in same TMS stage
    else:
        to_status = "advanced"
        tms_stage_key = "tms_status_advanced"

    # Update application
    application.status = to_status
    application.advanced_by = user.get("id")
    application.advanced_at = datetime.utcnow()

    # Queue TMS sync job if we have a stage to sync
    if tms_stage_key:
        tms_stage_id = get_setting_value(db, tms_stage_key)
        if tms_stage_id:
            # Set sync status to pending
            application.tms_sync_status = "pending"
            application.tms_sync_error = None

            # Queue the TMS sync job
            sync_job = Job(
                application_id=application_id,
                job_type="update_workday_stage",
                priority=3,  # Higher priority for sync jobs
                payload=json.dumps({
                    "stage_id": tms_stage_id,
                    "action": "advance",
                }),
            )
            db.add(sync_job)
            logger.info(
                "Queued Workday sync job for advance",
                application_id=application_id,
                stage_id=tms_stage_id,
            )
        else:
            logger.warning(
                "TMS stage not configured - Workday sync skipped",
                application_id=application_id,
                setting_key=tms_stage_key,
            )

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
    logger.info(
        "Reject request received",
        application_id=application_id,
        reason_code=data.reason_code.value,
        user_id=user.get("id"),
    )

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

    # Look up the rejection reason to get external_id for TMS sync
    reason_code = data.reason_code.value
    rejection_reason = db.query(RejectionReason).filter(
        RejectionReason.code == reason_code,
        RejectionReason.is_active == True,
    ).first()

    # Update application
    application.status = to_status
    application.rejection_reason_code = reason_code
    application.rejected_by = user.get("id")
    application.rejected_at = datetime.utcnow()

    # Queue TMS sync job if we have the external disposition ID
    if rejection_reason and rejection_reason.external_id:
        # Set sync status to pending
        application.tms_sync_status = "pending"
        application.tms_sync_error = None

        # Queue the TMS sync job
        sync_job = Job(
            application_id=application_id,
            job_type="update_workday_stage",
            priority=3,  # Higher priority for sync jobs
            payload=json.dumps({
                "disposition_id": rejection_reason.external_id,
                "action": "reject",
            }),
        )
        db.add(sync_job)
        logger.info(
            "Queued Workday sync job for rejection",
            application_id=application_id,
            disposition_id=rejection_reason.external_id,
        )
    else:
        # No sync job queued - log why
        if not rejection_reason:
            logger.warning(
                "Rejection reason not found in database - Workday sync skipped",
                application_id=application_id,
                reason_code=reason_code,
            )
        elif not rejection_reason.external_id:
            logger.warning(
                "Rejection reason has no external_id - Workday sync skipped",
                application_id=application_id,
                reason_code=reason_code,
            )

    # Log decision (no comment stored - discovery liability)
    decision = ApplicationDecision(
        application_id=application_id,
        action="reject",
        from_status=from_status,
        to_status=to_status,
        reason_code=reason_code,
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
            "reason_code": reason_code,
        }),
    )
    db.add(activity)

    db.commit()

    logger.info(
        "Application rejected",
        application_id=application_id,
        reason_code=reason_code,
        user_id=user.get("id"),
    )

    return DecisionResponse(
        success=True,
        application_id=application_id,
        action="reject",
        from_status=from_status,
        to_status=to_status,
        message=f"Application rejected with reason: {reason_code}",
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


@router.post("/{application_id}/unreject", response_model=DecisionResponse)
async def unreject_application(
    application_id: int,
    data: UnrejectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Unreject an application (move back to ready_for_review).

    WARNING: This action does NOT sync to Workday. The candidate will
    remain rejected in Workday. A comment is required to explain why
    the unreject is needed.

    This is an unusual action that should only be used when:
    - The wrong candidate was rejected by mistake
    - New information warrants reconsideration
    """
    # Use row locking to prevent race conditions
    application = db.query(Application).filter(Application.id == application_id).with_for_update().first()
    if not application:
        raise NotFoundError("Application", application_id)

    if application.status != "rejected":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot unreject application with status '{application.status}'. Only rejected applications can be unrejected.",
        )

    # Find the status before rejection from the decision audit trail
    last_rejection = (
        db.query(ApplicationDecision)
        .filter(
            ApplicationDecision.application_id == application_id,
            ApplicationDecision.action == "reject",
        )
        .order_by(ApplicationDecision.created_at.desc())
        .first()
    )

    from_status = application.status
    # Restore to status before rejection, or default to ready_for_review
    to_status = last_rejection.from_status if last_rejection else "ready_for_review"

    # Update application
    application.status = to_status
    # Keep rejection_reason_code for audit trail but clear rejected_by/at
    application.rejected_by = None
    application.rejected_at = None

    # Log decision WITH comment (unusual action needs audit trail)
    decision = ApplicationDecision(
        application_id=application_id,
        action="unreject",
        from_status=from_status,
        to_status=to_status,
        comment=data.comment,  # Store the justification
        user_id=user.get("id", 0),
    )
    db.add(decision)

    # Log activity
    activity = Activity(
        action="application_unrejected",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "from_status": from_status,
            "comment": data.comment,
            "workday_synced": False,  # Explicitly note this is local-only
        }),
    )
    db.add(activity)

    db.commit()

    logger.info(
        "Application unrejected (local only - not synced to Workday)",
        application_id=application_id,
        user_id=user.get("id"),
        comment=data.comment,
    )

    return DecisionResponse(
        success=True,
        application_id=application_id,
        action="unreject",
        from_status=from_status,
        to_status=to_status,
        message="Application moved back to review. Note: This change was NOT synced to Workday.",
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


# Interview endpoints

@router.post("/{application_id}/prepare-interview", response_model=PrepareInterviewResponse)
async def prepare_interview(
    application_id: int,
    data: PrepareInterviewRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Prepare an interview for an application (creates draft, returns preview).

    This is step 1 of the 2-step send flow:
    1. prepare-interview: Creates draft interview, returns email preview
    2. activate-interview: Sends email or activates link

    The interview is created with status='draft' and is not accessible
    to the candidate until activated.
    """
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Cancel any existing draft interviews (user is starting fresh)
    db.query(Interview).filter(
        Interview.application_id == application_id,
        Interview.status == "draft",
    ).update({"status": "cancelled"})

    # Determine email address (required for email mode, optional for link_only)
    candidate_email = data.email_override or application.candidate_email
    if data.mode == "email" and not candidate_email:
        raise HTTPException(
            status_code=400,
            detail="No email address available. Please provide email_override.",
        )

    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.expiry_days)

    # Create interview with status='draft'
    interview = Interview(
        application_id=application_id,
        interview_type="self_service",
        token=token,
        token_expires_at=expires_at,
        status="draft",
        persona_id=data.persona_id,
        candidate_email=candidate_email,  # May be None for link_only
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    # Build interview URL
    interview_url = f"{settings.FRONTEND_URL}/interview/{token}"

    # Generate email preview only for email mode
    email_preview = None
    if data.mode == "email" and candidate_email:
        recruiter_name = None
        if application.requisition.recruiter:
            recruiter_name = application.requisition.recruiter.name

        email_preview = generate_interview_email_preview(
            candidate_email=candidate_email,
            candidate_name=application.candidate_name,
            position_title=application.requisition.name,
            interview_url=interview_url,
            recruiter_name=recruiter_name,
            expiry_days=data.expiry_days,
        )

    logger.info(
        "Interview prepared (draft)",
        interview_id=interview.id,
        application_id=application_id,
        mode=data.mode,
        user_id=user.get("id"),
    )

    return PrepareInterviewResponse(
        interview_id=interview.id,
        interview_token=token,
        interview_url=interview_url,
        expires_at=expires_at,
        email_preview=email_preview,
    )


@router.post("/{application_id}/activate-interview", response_model=ActivateInterviewResponse)
async def activate_interview(
    application_id: int,
    data: ActivateInterviewRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Activate an interview (send email or just make link active).

    This is step 2 of the 2-step send flow.

    method='email': Send email invitation, set status='scheduled'
    method='link_only': Just activate the link (for manual distribution)
    """
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Find the draft interview
    interview = db.query(Interview).filter(
        Interview.application_id == application_id,
        Interview.status == "draft",
    ).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail="No draft interview found. Call prepare-interview first.",
        )

    # Determine final email address
    final_email = data.email_override or interview.candidate_email
    if data.method == "email" and not final_email:
        raise HTTPException(
            status_code=400,
            detail="No email address available for sending.",
        )

    # Calculate how many days were originally requested
    original_expiry_days = 7  # Default
    if interview.token_expires_at and interview.created_at:
        original_expiry_days = (interview.token_expires_at.replace(tzinfo=timezone.utc) - interview.created_at.replace(tzinfo=timezone.utc)).days
        if original_expiry_days < 1:
            original_expiry_days = 7

    # Reset expiration to start from now (so candidate gets full duration)
    interview.token_expires_at = datetime.now(timezone.utc) + timedelta(days=original_expiry_days)
    interview.status = "scheduled"

    # Update email if overridden at activation time
    if data.email_override:
        interview.candidate_email = data.email_override

    # Build interview URL
    interview_url = f"{settings.FRONTEND_URL}/interview/{interview.token}"

    email_sent = False
    email_sent_to = None

    if data.method == "email":
        # Send email via SES
        try:
            from api.integrations.ses import SESService
            from api.endpoints.settings import get_setting_value

            # Get email settings from database (falls back to config defaults)
            from_email = get_setting_value(db, "email_from_address", "")
            from_name = get_setting_value(db, "email_from_name", "")

            ses = SESService(
                from_email=from_email if from_email else None,
                from_name=from_name if from_name else None,
            )
            recruiter_email = None
            recruiter_name = None
            if application.requisition.recruiter:
                recruiter_email = application.requisition.recruiter.email
                recruiter_name = application.requisition.recruiter.name

            # Use custom HTML/subject if provided, otherwise use template
            if data.custom_html and data.custom_subject:
                await ses.send_email(
                    to=final_email,
                    subject=data.custom_subject,
                    html_body=data.custom_html,
                    reply_to=recruiter_email,
                )
            else:
                await ses.send_interview_invite(
                    to=final_email,
                    candidate_name=application.candidate_name,
                    position=application.requisition.name,
                    interview_url=interview_url,
                    recruiter_name=recruiter_name,
                    recruiter_email=recruiter_email,
                    expires_in_days=7,
                )

            interview.invite_sent_at = datetime.now(timezone.utc)
            email_sent = True
            email_sent_to = final_email

            logger.info(
                "Interview email sent",
                interview_id=interview.id,
                to=final_email,
                custom_email=bool(data.custom_html),
            )

        except Exception as e:
            logger.error("Failed to send interview email", error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send email: {str(e)}",
            )

    db.commit()

    # Log activity
    activity = Activity(
        action="interview_activated" if data.method == "link_only" else "interview_sent",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "interview_id": interview.id,
            "method": data.method,
            "email_sent": email_sent,
            "email_sent_to": email_sent_to,
        }),
    )
    db.add(activity)
    db.commit()

    logger.info(
        "Interview activated",
        interview_id=interview.id,
        method=data.method,
        email_sent=email_sent,
    )

    return ActivateInterviewResponse(
        interview_id=interview.id,
        interview_url=interview_url,
        expires_at=interview.token_expires_at,
        email_sent=email_sent,
        email_sent_to=email_sent_to,
    )


@router.post("/{application_id}/start-proxy-interview", response_model=StartProxyInterviewResponse)
async def start_proxy_interview(
    application_id: int,
    data: StartProxyInterviewRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Start a proxy interview (recruiter conducts on candidate's behalf).

    Proxy interviews are conducted by recruiters who type the candidate's
    responses during a phone call. The AI frames questions in 3rd person.

    No email or token is generated - the recruiter uses their authenticated
    session to conduct the interview.
    """
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise NotFoundError("Application", application_id)

    # Check if there's already an active interview
    existing = db.query(Interview).filter(
        Interview.application_id == application_id,
        Interview.status.in_(["in_progress"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Application already has an interview in progress (id={existing.id})",
        )

    # Create proxy interview
    interview = Interview(
        application_id=application_id,
        interview_type="proxy",
        status="in_progress",
        persona_id=data.persona_id,
        recruiter_id=user.get("id"),
        started_at=datetime.now(timezone.utc),
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    # Generate initial greeting using InterviewService
    service = InterviewService(db)
    initial_message = await service.start_interview(
        interview_id=interview.id,
        interview_type="proxy",
    )

    # Log activity
    activity = Activity(
        action="proxy_interview_started",
        application_id=application_id,
        requisition_id=application.requisition_id,
        recruiter_id=user.get("id"),
        details=json.dumps({
            "interview_id": interview.id,
        }),
    )
    db.add(activity)
    db.commit()

    logger.info(
        "Proxy interview started",
        interview_id=interview.id,
        application_id=application_id,
        recruiter_id=user.get("id"),
    )

    return StartProxyInterviewResponse(
        interview_id=interview.id,
        status=interview.status,
        initial_message=MessageResponse(
            id=initial_message.id,
            role=initial_message.role,
            content=initial_message.content,
            created_at=initial_message.created_at,
        ),
    )
