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

# Configuration models
from .prompts import Prompt
from .personas import Persona
from .settings import Setting, DEFAULT_SETTINGS

# Queue model
from .jobs import Job

# Audit models
from .activities import Activity

# Email models
from .email_templates import EmailTemplate
from .email_log import EmailLog

# Report templates
from .report_templates import ReportTemplate

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
    # Configuration
    "Prompt",
    "Persona",
    "Setting",
    "DEFAULT_SETTINGS",
    # Queue
    "Job",
    # Audit
    "Activity",
    # Email
    "EmailTemplate",
    "EmailLog",
    # Reports
    "ReportTemplate",
]
