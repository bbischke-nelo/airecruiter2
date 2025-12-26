"""API endpoints for AIRecruiter v2."""

from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router
from .recruiters import router as recruiters_router
from .requisitions import router as requisitions_router
from .applications import router as applications_router
from .interviews import router as interviews_router
from .public_interviews import router as public_interviews_router
from .prompts import router as prompts_router
from .personas import router as personas_router
from .settings import router as settings_router
from .queue import router as queue_router
from .logs import router as logs_router
from .email_templates import router as email_templates_router
from .report_templates import router as report_templates_router
from .workday_config import router as workday_config_router

# Create main API router
api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(recruiters_router, prefix="/recruiters", tags=["Recruiters"])
api_router.include_router(requisitions_router, prefix="/requisitions", tags=["Requisitions"])
api_router.include_router(applications_router, prefix="/applications", tags=["Applications"])
api_router.include_router(interviews_router, prefix="/interviews", tags=["Interviews"])
api_router.include_router(public_interviews_router, prefix="/public/interviews", tags=["Public Interviews"])
api_router.include_router(prompts_router, prefix="/prompts", tags=["Prompts"])
api_router.include_router(personas_router, prefix="/personas", tags=["Personas"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(queue_router, prefix="/queue", tags=["Queue"])
api_router.include_router(logs_router, prefix="/logs", tags=["Logs"])
api_router.include_router(email_templates_router, prefix="/email-templates", tags=["Email Templates"])
api_router.include_router(report_templates_router, prefix="/report-templates", tags=["Report Templates"])
api_router.include_router(workday_config_router, prefix="/workday", tags=["Workday Configuration"])

__all__ = ["api_router"]
