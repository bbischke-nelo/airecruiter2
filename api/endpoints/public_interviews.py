"""Public interview endpoints (no authentication required)."""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends

from api.config.database import get_db
from api.models import Interview, Application, Requisition, Message
from api.schemas.interviews import (
    PublicInterviewInfo,
    PublicMessageRequest,
    PublicMessageResponse,
    MessageResponse,
)
from api.services.interview_service import InterviewService

logger = structlog.get_logger()
router = APIRouter()


def get_interview_by_token(token: str, db: Session) -> Interview:
    """Get interview by token or raise 404."""
    interview = (
        db.query(Interview)
        .join(Application)
        .join(Requisition)
        .filter(Interview.token == token)
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Check expiration
    if interview.token_expires_at and interview.token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Interview link has expired")

    # Check status
    if interview.status in ["completed", "abandoned"]:
        raise HTTPException(status_code=410, detail="Interview is no longer active")

    return interview


@router.get("/{token}", response_model=PublicInterviewInfo)
async def get_public_interview(
    token: str,
    db: Session = Depends(get_db),
):
    """Get interview info for candidate (no auth required)."""
    interview = get_interview_by_token(token, db)

    return PublicInterviewInfo(
        candidate_name=interview.application.candidate_name.split()[0],  # First name only
        position_title=interview.application.requisition.name,
        company_name="CCFS",
        status=interview.status,
        expires_at=interview.token_expires_at,
    )


@router.post("/{token}/start")
async def start_interview(
    token: str,
    db: Session = Depends(get_db),
):
    """Start an interview session."""
    # Use row locking to prevent race condition from double-clicks
    interview = (
        db.query(Interview)
        .filter(Interview.token == token)
        .with_for_update()
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Check expiration
    if interview.token_expires_at and interview.token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Interview link has expired")

    # Check status
    if interview.status in ["completed", "abandoned"]:
        raise HTTPException(status_code=410, detail="Interview is no longer active")

    if interview.status == "in_progress":
        # Get existing messages
        messages = (
            db.query(Message)
            .filter(Message.interview_id == interview.id)
            .order_by(Message.created_at)
            .all()
        )
        if messages:
            return {
                "message": "Interview already in progress",
                "initial_message": MessageResponse(
                    id=messages[0].id,
                    role=messages[0].role,
                    content=messages[0].content,
                    created_at=messages[0].created_at,
                ),
            }
        return {"message": "Interview already in progress"}

    # Use InterviewService to start interview with proper greeting
    service = InterviewService(db)
    initial_message = await service.start_interview(
        interview_id=interview.id,
        interview_type="self_service",
    )

    logger.info("Interview started via public link", interview_id=interview.id)

    return {
        "message": "Interview started",
        "initial_message": MessageResponse(
            id=initial_message.id,
            role=initial_message.role,
            content=initial_message.content,
            created_at=initial_message.created_at,
        ),
    }


@router.post("/{token}/messages", response_model=PublicMessageResponse)
async def send_message(
    token: str,
    data: PublicMessageRequest,
    db: Session = Depends(get_db),
):
    """Send a message in the interview."""
    interview = get_interview_by_token(token, db)

    if interview.status != "in_progress":
        raise HTTPException(status_code=400, detail="Interview is not in progress")

    # Use InterviewService to process message
    service = InterviewService(db)
    user_message, assistant_message = await service.process_message(
        interview_id=interview.id,
        user_message=data.content,
    )

    # Check if interview completed
    db.refresh(interview)
    is_complete = interview.status == "completed"

    return PublicMessageResponse(
        user_message=MessageResponse(
            id=user_message.id,
            role=user_message.role,
            content=user_message.content,
            created_at=user_message.created_at,
        ),
        assistant_message=MessageResponse(
            id=assistant_message.id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at,
        ),
        is_complete=is_complete,
    )


@router.post("/{token}/request-human")
async def request_human(
    token: str,
    db: Session = Depends(get_db),
):
    """Request to speak with a human recruiter."""
    interview = get_interview_by_token(token, db)

    interview.human_requested = True
    interview.human_requested_at = datetime.now(timezone.utc)

    # Also flag on application
    interview.application.human_requested = True

    db.commit()

    logger.info("Human requested", interview_id=interview.id)

    return {
        "message": "Your request to speak with a human recruiter has been noted. Someone will reach out to you soon."
    }


@router.get("/{token}/messages", response_model=list[MessageResponse])
async def get_messages(
    token: str,
    db: Session = Depends(get_db),
):
    """Get all messages for an interview."""
    interview = get_interview_by_token(token, db)

    messages = (
        db.query(Message)
        .filter(Message.interview_id == interview.id)
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
