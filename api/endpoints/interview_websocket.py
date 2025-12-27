"""WebSocket endpoint for real-time interview chat."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Optional, Tuple

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from api.config.database import SessionLocal
from api.models import Interview, Application, Requisition, Message, Persona, Prompt, Analysis

logger = structlog.get_logger()
router = APIRouter()

# Completion tags that the AI uses to signal interview state
COMPLETE_TAG = "[INTERVIEW_COMPLETE]"
HUMAN_TAG = "[HUMAN_REQUESTED]"

# Path to default prompts
PROMPTS_DIR = Path(__file__).parent.parent / "config" / "prompts"


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, token: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[token] = websocket

    def disconnect(self, token: str):
        if token in self.active_connections:
            del self.active_connections[token]

    async def send_message(self, token: str, message: dict):
        if token in self.active_connections:
            await self.active_connections[token].send_json(message)


manager = ConnectionManager()


def get_interview_by_token(token: str, db: Session) -> Optional[Interview]:
    """Get interview by token."""
    return (
        db.query(Interview)
        .join(Application)
        .join(Requisition)
        .filter(Interview.token == token)
        .first()
    )


def validate_interview(interview: Interview) -> Tuple[bool, str]:
    """Validate interview is active and not expired."""
    if not interview:
        return False, "Interview not found"

    if interview.token_expires_at:
        # Ensure timezone-aware comparison (database may return naive datetime)
        expires_at = interview.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return False, "Interview link has expired"

    if interview.status in ["completed", "abandoned"]:
        return False, "Interview is no longer active"

    return True, ""


def load_interview_prompt(db: Session, interview_type: str = "self_service") -> str:
    """Load interview prompt from database or fall back to file.

    Args:
        db: Database session
        interview_type: Either 'self_service' or 'recruiter_assisted'

    Returns:
        The prompt template string
    """
    # Try to load from database first
    prompt_name = f"{interview_type}_interview"
    db_prompt = db.query(Prompt).filter(
        Prompt.name == prompt_name,
        Prompt.is_active == True
    ).first()

    if db_prompt and db_prompt.content:
        return db_prompt.content

    # Fall back to file
    filename = "self_service_interview.md" if interview_type == "self_service" else "interview.md"
    prompt_path = PROMPTS_DIR / filename

    if prompt_path.exists():
        return prompt_path.read_text()

    # Ultimate fallback - basic prompt
    return """You are an AI assistant conducting a screening interview.
Be professional and friendly. Ask about their background, experience, and interest in the role.
When you've gathered enough information (after 15-25 exchanges), end with a thank you and include [INTERVIEW_COMPLETE] on its own line."""


def substitute_prompt_variables(template: str, interview: Interview, db: Session) -> str:
    """Substitute variables in the prompt template.

    Variables supported:
    - ${candidateName} - Candidate's full name
    - ${requisitionTitle} - Job title
    - ${requisitionBriefDescription} - Job description
    - ${todayDate} - Current date
    - ${resumeSummary} - Summary from resume analysis
    - ${interviewModeContext} - Context for self-service vs recruiter mode
    - ${openingScript} - Opening greeting script
    - ${additionalInstructions} - Any additional instructions
    """
    # Get resume summary from analysis if available
    analysis = db.query(Analysis).filter(
        Analysis.application_id == interview.application_id
    ).first()

    resume_summary = ""
    if analysis and analysis.relevance_summary:
        resume_summary = f"Resume Summary: {analysis.relevance_summary}"

    # Build interview mode context
    interview_mode_context = """This is a SELF-SERVICE INTERVIEW. You are speaking directly with the candidate.
- Be warm and professional - this is their first real interaction with the company
- Speak directly to the candidate in second person (you/your)
- If they seem nervous, reassure them: "Take your time, there's no rush"
- The value prop: completing this gets them directly to the hiring manager"""

    # Opening script
    opening_script = f"""Hi {interview.application.candidate_name.split()[0]}! Thanks for taking the time to chat with me about the {interview.application.requisition.name} position. I'm an AI assistant helping with initial screening interviews.

Before we begin, just so you know: your responses will be recorded and reviewed as part of our hiring process.

This should take about 15-20 minutes. I'll ask you some questions about your background and experience. Ready to get started?"""

    # Build substitution dictionary
    variables = {
        "candidateName": interview.application.candidate_name,
        "requisitionTitle": interview.application.requisition.name,
        "requisitionBriefDescription": interview.application.requisition.description or "Not provided",
        "todayDate": datetime.now().strftime("%B %d, %Y"),
        "resumeSummary": resume_summary,
        "interviewModeContext": interview_mode_context,
        "openingScript": opening_script,
        "additionalInstructions": "",
    }

    # Use string.Template for safe substitution
    try:
        return Template(template).safe_substitute(variables)
    except Exception as e:
        logger.warning("Failed to substitute prompt variables", error=str(e))
        return template


def check_and_strip_tags(content: str) -> Tuple[Optional[str], Optional[str], str]:
    """Check if the AI's message contains completion tags and strip them.

    Returns:
        Tuple of (complete_reason, human_reason, cleaned_content)
        - complete_reason: Set if interview should complete normally
        - human_reason: Set if human was requested
        - cleaned_content: Content with tags removed
    """
    cleaned = content
    complete_reason = None
    human_reason = None

    if HUMAN_TAG in content:
        human_reason = "Candidate requested human recruiter"
        cleaned = content.replace(HUMAN_TAG, "").strip()
    elif COMPLETE_TAG in content:
        complete_reason = "Interview completed normally"
        cleaned = content.replace(COMPLETE_TAG, "").strip()

    return complete_reason, human_reason, cleaned


async def generate_claude_response(
    messages: list[dict],
    system_prompt: str,
    interview: Interview,
) -> str:
    """Generate AI response using Claude with full system prompt."""
    from api.integrations.claude import ClaudeClient, ClaudeError

    try:
        client = ClaudeClient()

        # Claude requires at least one user message
        # If no messages, ask for an opening greeting
        if not messages:
            messages = [{"role": "user", "content": "Please begin the interview with your opening greeting."}]

        # Use the messages API with system prompt
        response = client.client.messages.create(
            model=client.model,
            max_tokens=1000,
            system=system_prompt,
            messages=messages,
        )

        return response.content[0].text

    except ClaudeError as e:
        logger.error("Claude response generation failed", error=str(e))
        return "I apologize, but I'm having technical difficulties. Please continue with your response."
    except Exception as e:
        logger.error("Unexpected error in response generation", error=str(e))
        return "I apologize for the interruption. Please go ahead with your answer."


@router.websocket("/ws/interviews/{token}")
async def interview_websocket(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time interview chat.

    Protocol:
    - Client connects with interview token
    - Server validates token and sends interview info
    - Client sends: {"type": "message", "content": "..."}
    - Server responds with: {"type": "message", "role": "assistant", "content": "...", "id": 123}
    - Server sends: {"type": "typing", "status": true/false} during response generation
    - Client sends: {"type": "end"} to end interview
    - Server sends: {"type": "completed"} when interview ends

    The AI will include [INTERVIEW_COMPLETE] or [HUMAN_REQUESTED] tags when appropriate.
    These tags are stripped before sending to the client.
    """
    db = SessionLocal()

    try:
        # Validate token
        interview = get_interview_by_token(token, db)
        is_valid, error_msg = validate_interview(interview)

        if not is_valid:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": error_msg})
            await websocket.close(code=4000)
            return

        # Accept connection
        await manager.connect(token, websocket)
        logger.info("WebSocket connected", interview_id=interview.id, token=token[:8])

        # Send interview info
        await websocket.send_json({
            "type": "connected",
            "interview": {
                "id": interview.id,
                "candidateName": interview.application.candidate_name.split()[0],
                "positionTitle": interview.application.requisition.name,
                "status": interview.status,
            },
        })

        # Load and prepare the system prompt
        interview_type = interview.interview_type or "self_service"
        prompt_template = load_interview_prompt(db, interview_type)
        system_prompt = substitute_prompt_variables(prompt_template, interview, db)

        # Start interview if not already started
        if interview.status == "scheduled":
            interview.status = "in_progress"
            interview.started_at = datetime.now(timezone.utc)
            db.commit()

        # Check if we need to generate a greeting (no messages yet)
        existing_count = (
            db.query(Message)
            .filter(Message.interview_id == interview.id)
            .count()
        )

        logger.info(
            "Checking greeting generation",
            interview_id=interview.id,
            status=interview.status,
            existing_messages=existing_count,
        )

        if existing_count == 0 and interview.status == "in_progress":
            logger.info("Generating greeting", interview_id=interview.id)
            # Generate opening from Claude using the system prompt
            await websocket.send_json({"type": "typing", "status": True})

            try:
                initial_response = await generate_claude_response(
                    messages=[],  # Empty - just get the opening
                    system_prompt=system_prompt,
                    interview=interview,
                )
                logger.info("Claude response received", interview_id=interview.id, response_length=len(initial_response))
            except Exception as e:
                logger.error("Failed to generate greeting", interview_id=interview.id, error=str(e))
                initial_response = "Hello! Thanks for joining us today. I'm here to learn more about your background and experience. Ready to get started?"

            # Check for tags (unlikely in opening but be safe)
            _, _, cleaned_response = check_and_strip_tags(initial_response)

            await websocket.send_json({"type": "typing", "status": False})

            greeting_msg = Message(
                interview_id=interview.id,
                role="assistant",
                content=cleaned_response,
            )
            db.add(greeting_msg)
            db.commit()
            db.refresh(greeting_msg)

            logger.info("Greeting saved and sending", interview_id=interview.id, message_id=greeting_msg.id)

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": cleaned_response,
                "id": greeting_msg.id,
                "createdAt": greeting_msg.created_at.isoformat(),
            })

        # Load existing messages
        existing_messages = (
            db.query(Message)
            .filter(Message.interview_id == interview.id)
            .order_by(Message.created_at)
            .all()
        )

        logger.info(
            "Sending message history",
            interview_id=interview.id,
            message_count=len(existing_messages),
        )

        if existing_messages:
            await websocket.send_json({
                "type": "history",
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "createdAt": m.created_at.isoformat(),
                    }
                    for m in existing_messages
                ],
            })

        # Message loop
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                # Save user message
                user_msg = Message(
                    interview_id=interview.id,
                    role="user",
                    content=content,
                )
                db.add(user_msg)
                db.commit()
                db.refresh(user_msg)

                await websocket.send_json({
                    "type": "message_received",
                    "id": user_msg.id,
                    "createdAt": user_msg.created_at.isoformat(),
                })

                # Indicate typing
                await websocket.send_json({"type": "typing", "status": True})

                # Build conversation history for Claude
                all_messages = (
                    db.query(Message)
                    .filter(Message.interview_id == interview.id)
                    .order_by(Message.created_at)
                    .all()
                )

                claude_messages = [
                    {"role": m.role, "content": m.content}
                    for m in all_messages
                ]

                # Generate AI response (AI decides when to end via tags)
                ai_response = await generate_claude_response(
                    messages=claude_messages,
                    system_prompt=system_prompt,
                    interview=interview,
                )

                # Check for completion tags
                complete_reason, human_reason, cleaned_response = check_and_strip_tags(ai_response)

                # Stop typing indicator
                await websocket.send_json({"type": "typing", "status": False})

                # Save assistant message (cleaned version)
                assistant_msg = Message(
                    interview_id=interview.id,
                    role="assistant",
                    content=cleaned_response,
                )
                db.add(assistant_msg)
                db.commit()
                db.refresh(assistant_msg)

                await websocket.send_json({
                    "type": "message",
                    "role": "assistant",
                    "content": cleaned_response,
                    "id": assistant_msg.id,
                    "createdAt": assistant_msg.created_at.isoformat(),
                })

                # Handle completion
                if complete_reason:
                    interview.status = "completed"
                    interview.completed_at = datetime.now(timezone.utc)
                    db.commit()

                    logger.info("Interview completed", interview_id=interview.id, reason=complete_reason)
                    await websocket.send_json({"type": "completed"})
                    break

                if human_reason:
                    interview.human_requested = True
                    interview.human_requested_at = datetime.now(timezone.utc)
                    interview.application.human_requested = True
                    db.commit()

                    logger.info("Human requested by AI detection", interview_id=interview.id)
                    await websocket.send_json({
                        "type": "human_requested",
                        "message": "A recruiter will reach out to you soon.",
                    })

            elif msg_type == "end":
                # User explicitly ends interview - generate a graceful closing
                await websocket.send_json({"type": "typing", "status": True})

                # Ask Claude to wrap up the interview
                all_messages = (
                    db.query(Message)
                    .filter(Message.interview_id == interview.id)
                    .order_by(Message.created_at)
                    .all()
                )
                claude_messages = [
                    {"role": m.role, "content": m.content}
                    for m in all_messages
                ]
                # Add context that user wants to end
                claude_messages.append({
                    "role": "user",
                    "content": "[The candidate has indicated they need to end the interview now. Please provide a brief, graceful closing that thanks them for their time and lets them know next steps.]"
                })

                closing_response = await generate_claude_response(
                    messages=claude_messages,
                    system_prompt=system_prompt + "\n\nIMPORTANT: The candidate needs to end now. Provide a brief, warm closing. Do NOT include [INTERVIEW_COMPLETE] tag - the system will handle that.",
                    interview=interview,
                )

                # Strip any tags just in case
                _, _, cleaned_closing = check_and_strip_tags(closing_response)

                await websocket.send_json({"type": "typing", "status": False})

                # Save closing message
                closing_msg = Message(
                    interview_id=interview.id,
                    role="assistant",
                    content=cleaned_closing,
                )
                db.add(closing_msg)

                interview.status = "completed"
                interview.completed_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(closing_msg)

                await websocket.send_json({
                    "type": "message",
                    "role": "assistant",
                    "content": cleaned_closing,
                    "id": closing_msg.id,
                    "createdAt": closing_msg.created_at.isoformat(),
                })
                await websocket.send_json({"type": "completed"})
                logger.info("Interview ended by user with graceful closing", interview_id=interview.id)
                break

            elif msg_type == "request_human":
                # User requests human recruiter - acknowledge and wrap up
                await websocket.send_json({"type": "typing", "status": True})

                # Generate acknowledgment
                all_messages = (
                    db.query(Message)
                    .filter(Message.interview_id == interview.id)
                    .order_by(Message.created_at)
                    .all()
                )
                claude_messages = [
                    {"role": m.role, "content": m.content}
                    for m in all_messages
                ]
                claude_messages.append({
                    "role": "user",
                    "content": "[The candidate has requested to speak with a human recruiter instead. Please acknowledge their request warmly and let them know someone will reach out soon.]"
                })

                human_response = await generate_claude_response(
                    messages=claude_messages,
                    system_prompt=system_prompt + "\n\nIMPORTANT: The candidate wants to speak with a human. Acknowledge this warmly, thank them for their time, and assure them a recruiter will reach out soon. Keep it brief.",
                    interview=interview,
                )

                _, _, cleaned_human = check_and_strip_tags(human_response)

                await websocket.send_json({"type": "typing", "status": False})

                # Save acknowledgment message
                human_msg = Message(
                    interview_id=interview.id,
                    role="assistant",
                    content=cleaned_human,
                )
                db.add(human_msg)

                interview.human_requested = True
                interview.human_requested_at = datetime.now(timezone.utc)
                interview.application.human_requested = True
                db.commit()
                db.refresh(human_msg)

                await websocket.send_json({
                    "type": "message",
                    "role": "assistant",
                    "content": cleaned_human,
                    "id": human_msg.id,
                    "createdAt": human_msg.created_at.isoformat(),
                })
                await websocket.send_json({
                    "type": "human_requested",
                    "message": "A recruiter will reach out to you soon.",
                })
                logger.info("Human requested via WebSocket", interview_id=interview.id)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", token=token[:8])
    except Exception as e:
        logger.error("WebSocket error", error=str(e), token=token[:8])
        try:
            await websocket.send_json({"type": "error", "message": "Server error"})
        except:
            pass
    finally:
        manager.disconnect(token)
        db.close()
