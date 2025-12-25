"""Pydantic schemas for API request/response validation.

All schemas use CamelCase for JSON field names (via alias_generator).
"""

from .base import CamelModel, PaginatedResponse, PaginationMeta, ErrorResponse

# Re-export all schemas
from .recruiters import (
    RecruiterCreate,
    RecruiterUpdate,
    RecruiterResponse,
    RecruiterListItem,
)
from .requisitions import (
    RequisitionCreate,
    RequisitionUpdate,
    RequisitionResponse,
    RequisitionListItem,
    SyncResponse,
)
from .applications import (
    ApplicationListItem,
    ApplicationResponse,
    AnalysisResponse,
    ReprocessRequest,
    ReprocessResponse,
)
from .interviews import (
    InterviewCreate,
    InterviewListItem,
    InterviewResponse,
    MessageResponse,
    EvaluationResponse,
    PublicInterviewInfo,
    PublicMessageRequest,
    PublicMessageResponse,
)
from .prompts import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptListItem,
)
from .personas import (
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
    PersonaListItem,
)
from .credentials import (
    CredentialCreate,
    CredentialStatusResponse,
    CredentialTestResponse,
)
from .settings import (
    SettingsResponse,
    SettingsUpdate,
)
from .queue import (
    QueueItem,
    QueueStatusResponse,
    QueueAddRequest,
    QueueAddResponse,
)
from .activities import (
    ActivityResponse,
    ActivityListItem,
)

__all__ = [
    # Base
    "CamelModel",
    "PaginatedResponse",
    "PaginationMeta",
    "ErrorResponse",
    # Recruiters
    "RecruiterCreate",
    "RecruiterUpdate",
    "RecruiterResponse",
    "RecruiterListItem",
    # Requisitions
    "RequisitionCreate",
    "RequisitionUpdate",
    "RequisitionResponse",
    "RequisitionListItem",
    "SyncResponse",
    # Applications
    "ApplicationListItem",
    "ApplicationResponse",
    "AnalysisResponse",
    "ReprocessRequest",
    "ReprocessResponse",
    # Interviews
    "InterviewCreate",
    "InterviewListItem",
    "InterviewResponse",
    "MessageResponse",
    "EvaluationResponse",
    "PublicInterviewInfo",
    "PublicMessageRequest",
    "PublicMessageResponse",
    # Prompts
    "PromptCreate",
    "PromptUpdate",
    "PromptResponse",
    "PromptListItem",
    # Personas
    "PersonaCreate",
    "PersonaUpdate",
    "PersonaResponse",
    "PersonaListItem",
    # Credentials
    "CredentialCreate",
    "CredentialStatusResponse",
    "CredentialTestResponse",
    # Settings
    "SettingsResponse",
    "SettingsUpdate",
    # Queue
    "QueueItem",
    "QueueStatusResponse",
    "QueueAddRequest",
    "QueueAddResponse",
    # Activities
    "ActivityResponse",
    "ActivityListItem",
]
