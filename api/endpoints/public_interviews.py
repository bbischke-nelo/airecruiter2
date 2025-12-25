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
    interview = get_interview_by_token(token, db)

    if interview.status == "in_progress":
        return {"message": "Interview already in progress"}

    interview.status = "in_progress"
    interview.started_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Interview started", interview_id=interview.id)

    # Get initial greeting message if exists, or create one
    messages = db.query(Message).filter(Message.interview_id == interview.id).all()

    if not messages:
        # TODO: Generate initial greeting from persona
        initial_message = Message(
            interview_id=interview.id,
            role="assistant",
            content=f"Hello! Thank you for taking the time to interview for the {interview.application.requisition.name} position. I'm here to learn more about your experience and qualifications. Let's get started - can you tell me a bit about yourself and what interests you about this role?",
        )
        db.add(initial_message)
        db.commit()
        db.refresh(initial_message)

        return {
            "message": "Interview started",
            "initial_message": MessageResponse(
                id=initial_message.id,
                role=initial_message.role,
                content=initial_message.content,
                created_at=initial_message.created_at,
            ),
        }

    return {"message": "Interview resumed"}


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

    # Save user message
    user_message = Message(
        interview_id=interview.id,
        role="user",
        content=data.content,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # TODO: Call Claude API to generate response
    # For now, return a placeholder
    assistant_content = "Thank you for sharing that. [AI response will be generated here]"

    # Check if interview should end (TODO: implement logic)
    is_complete = False

    assistant_message = Message(
        interview_id=interview.id,
        role="assistant",
        content=assistant_content,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    if is_complete:
        interview.status = "completed"
        interview.completed_at = datetime.now(timezone.utc)
        db.commit()

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
