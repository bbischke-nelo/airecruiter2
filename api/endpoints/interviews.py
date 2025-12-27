"""Interview CRUD endpoints."""

import json
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.middleware.error_handler import NotFoundError
from api.models import Interview, Application, Requisition, Message, Evaluation, Job, Activity
from api.schemas.interviews import (
    InterviewCreate,
    InterviewListItem,
    InterviewResponse,
    MessageResponse,
    EvaluationResponse,
    ProxyMessageRequest,
    ProxyMessageResponse,
    EndProxyResponse,
)
from api.schemas.base import PaginatedResponse, PaginationMeta
from api.services.rbac import require_role
from api.services.interview_service import InterviewService

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=PaginatedResponse[InterviewListItem])
async def list_interviews(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    application_id: Optional[int] = Query(None),
    requisition_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """List all interviews with pagination."""
    query = db.query(Interview).join(Application).join(Requisition)

    # Filters
    if application_id:
        query = query.filter(Interview.application_id == application_id)
    if requisition_id:
        query = query.filter(Application.requisition_id == requisition_id)
    if status:
        query = query.filter(Interview.status == status)

    # Count total
    total = query.count()

    # Paginate
    interviews = query.order_by(Interview.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Get message counts
    interview_ids = [i.id for i in interviews]
    message_counts = dict(
        db.query(Message.interview_id, func.count(Message.id))
        .filter(Message.interview_id.in_(interview_ids))
        .group_by(Message.interview_id)
        .all()
    )

    items = [
        InterviewListItem(
            id=i.id,
            application_id=i.application_id,
            candidate_name=i.application.candidate_name,
            requisition_name=i.application.requisition.name,
            interview_type=i.interview_type,
            status=i.status,
            created_at=i.created_at,
            started_at=i.started_at,
            completed_at=i.completed_at,
            message_count=message_counts.get(i.id, 0),
        )
        for i in interviews
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


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get an interview by ID."""
    interview = (
        db.query(Interview)
        .join(Application)
        .join(Requisition)
        .filter(Interview.id == interview_id)
        .first()
    )
    if not interview:
        raise NotFoundError("Interview", interview_id)

    message_count = db.query(Message).filter(Message.interview_id == interview_id).count()

    return InterviewResponse(
        id=interview.id,
        application_id=interview.application_id,
        candidate_name=interview.application.candidate_name,
        requisition_name=interview.application.requisition.name,
        interview_type=interview.interview_type,
        status=interview.status,
        token=interview.token,
        token_expires_at=interview.token_expires_at,
        persona_id=interview.persona_id,
        created_at=interview.created_at,
        started_at=interview.started_at,
        completed_at=interview.completed_at,
        message_count=message_count,
    )


@router.get("/{interview_id}/messages", response_model=list[MessageResponse])
async def get_interview_messages(
    interview_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get all messages for an interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise NotFoundError("Interview", interview_id)

    messages = (
        db.query(Message)
        .filter(Message.interview_id == interview_id)
        .order_by(Message.created_at)
        .all()
    )

    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.get("/{interview_id}/evaluation", response_model=EvaluationResponse)
async def get_interview_evaluation(
    interview_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get evaluation for an interview."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise NotFoundError("Interview", interview_id)

    evaluation = db.query(Evaluation).filter(Evaluation.interview_id == interview_id).first()
    if not evaluation:
        raise NotFoundError("Evaluation", interview_id)

    return EvaluationResponse(
        id=evaluation.id,
        interview_id=evaluation.interview_id,
        reliability_score=evaluation.reliability_score,
        accountability_score=evaluation.accountability_score,
        professionalism_score=evaluation.professionalism_score,
        communication_score=evaluation.communication_score,
        technical_score=evaluation.technical_score,
        growth_potential_score=evaluation.growth_potential_score,
        overall_score=evaluation.overall_score,
        summary=evaluation.summary,
        strengths=json.loads(evaluation.strengths) if evaluation.strengths else [],
        weaknesses=json.loads(evaluation.weaknesses) if evaluation.weaknesses else [],
        red_flags=json.loads(evaluation.red_flags) if evaluation.red_flags else [],
        interview_highlights=json.loads(evaluation.interview_highlights) if evaluation.interview_highlights else [],
        recommendation=evaluation.recommendation,
        next_interview_focus=json.loads(evaluation.next_interview_focus) if evaluation.next_interview_focus else [],
        model_version=evaluation.model_version,
        created_at=evaluation.created_at,
    )


@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(
    data: InterviewCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Create a new interview (triggers send_interview job)."""
    application = db.query(Application).filter(Application.id == data.application_id).first()
    if not application:
        raise NotFoundError("Application", data.application_id)

    # Create job to send interview
    job = Job(
        application_id=data.application_id,
        job_type="send_interview",
        priority=5,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Interview creation queued", application_id=data.application_id, job_id=job.id)

    # Return placeholder - actual interview created by processor
    return InterviewResponse(
        id=0,  # Placeholder
        application_id=data.application_id,
        candidate_name=application.candidate_name,
        requisition_name=application.requisition.name,
        interview_type="self_service",
        status="scheduled",
        created_at=application.created_at,
        message_count=0,
    )


@router.post("/{interview_id}/send-invite")
async def resend_interview_invite(
    interview_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Resend interview invitation email."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise NotFoundError("Interview", interview_id)

    # Queue email resend
    job = Job(
        application_id=interview.application_id,
        job_type="send_interview",
        priority=5,
    )
    db.add(job)
    db.commit()

    logger.info("Interview invite resend queued", interview_id=interview_id)
    return {"message": "Invite resend queued"}


@router.post("/{interview_id}/proxy-message", response_model=ProxyMessageResponse)
async def send_proxy_message(
    interview_id: int,
    data: ProxyMessageRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Send a message in a proxy interview (recruiter typing on behalf of candidate)."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise NotFoundError("Interview", interview_id)

    # Validate this is a proxy interview
    if interview.interview_type != "proxy":
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for proxy interviews",
        )

    # Validate interview is in progress
    if interview.status != "in_progress":
        raise HTTPException(
            status_code=400,
            detail=f"Interview is not in progress (status: {interview.status})",
        )

    # Process message via InterviewService
    service = InterviewService(db)
    user_msg, ai_msg = await service.process_message(
        interview_id=interview_id,
        user_message=data.content,
    )

    # Check if interview completed
    db.refresh(interview)
    is_complete = interview.status == "completed"

    logger.info(
        "Proxy message processed",
        interview_id=interview_id,
        is_complete=is_complete,
    )

    return ProxyMessageResponse(
        user_message=MessageResponse(
            id=user_msg.id,
            role=user_msg.role,
            content=user_msg.content,
            created_at=user_msg.created_at,
        ),
        ai_response=MessageResponse(
            id=ai_msg.id,
            role=ai_msg.role,
            content=ai_msg.content,
            created_at=ai_msg.created_at,
        ),
        is_complete=is_complete,
    )


@router.post("/{interview_id}/end-proxy", response_model=EndProxyResponse)
async def end_proxy_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """End a proxy interview and queue evaluation."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise NotFoundError("Interview", interview_id)

    # Validate this is a proxy interview
    if interview.interview_type != "proxy":
        raise HTTPException(
            status_code=400,
            detail="This endpoint is only for proxy interviews",
        )

    # Validate interview can be ended
    if interview.status not in ("in_progress", "scheduled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot end interview with status: {interview.status}",
        )

    # End the interview
    service = InterviewService(db)
    interview = await service.end_interview(interview_id)

    # Queue evaluation job
    job = Job(
        application_id=interview.application_id,
        job_type="evaluate",
        priority=5,
    )
    db.add(job)

    # Log activity
    activity = Activity(
        application_id=interview.application_id,
        activity_type="interview_completed",
        details=f"Proxy interview completed (ID: {interview_id})",
    )
    db.add(activity)
    db.commit()

    # Get message count
    message_count = db.query(Message).filter(Message.interview_id == interview_id).count()

    logger.info(
        "Proxy interview ended",
        interview_id=interview_id,
        message_count=message_count,
    )

    return EndProxyResponse(
        interview_id=interview.id,
        status=interview.status,
        message_count=message_count,
        completed_at=interview.completed_at,
    )
