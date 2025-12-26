"""SQLAlchemy ORM models for AIRecruiter v2.

All models are imported here to ensure they're registered with Base.metadata
before any database operations.
"""

# Import base first
from api.config.database import Base

# Core models
from .recruiters import Recruiter
from .requisitions import Requisition
from .applications import Application
from .analyses import Analysis
from .interviews import Interview
from .messages import Message
from .evaluations import Evaluation
from .reports import Report
from .candidate_profiles import CandidateProfile

# Configuration models
from .prompts import Prompt
from .personas import Persona
from .settings import Setting, DEFAULT_SETTINGS

# Queue model
from .jobs import Job

# Audit models
from .activities import Activity
from .application_decisions import ApplicationDecision, VALID_REASON_CODES, REASON_CODES_REQUIRING_COMMENT

# Email models
from .email_templates import EmailTemplate
from .email_log import EmailLog

# Report templates
from .report_templates import ReportTemplate

# Rejection reasons
from .workday_config import RejectionReason, DEFAULT_REJECTION_REASONS

__all__ = [
    "Base",
    # Core
    "Recruiter",
    "Requisition",
    "Application",
    "Analysis",
    "Interview",
    "Message",
    "Evaluation",
    "Report",
    "CandidateProfile",
    # Configuration
    "Prompt",
    "Persona",
    "Setting",
    "DEFAULT_SETTINGS",
    # Queue
    "Job",
    # Audit
    "Activity",
    "ApplicationDecision",
    "VALID_REASON_CODES",
    "REASON_CODES_REQUIRING_COMMENT",
    # Email
    "EmailTemplate",
    "EmailLog",
    # Reports
    "ReportTemplate",
    # Workday configuration
    "RejectionReason",
    "DEFAULT_REJECTION_REASONS",
]
