"""Health check endpoints for monitoring."""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config.settings import settings
from api.config.database import get_db

logger = structlog.get_logger()
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    database: str
    workday: str
    processor: str


class DetailedHealthResponse(HealthResponse):
    """Detailed health check with component info."""
    components: dict


def check_database(db: Session) -> tuple[str, str | None]:
    """Check database connectivity."""
    try:
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        return "connected", None
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return "disconnected", str(e)


def check_workday() -> tuple[str, str | None]:
    """Check Workday API connectivity."""
    # TODO: Implement actual Workday health check
    if not settings.WORKDAY_TENANT_URL:
        return "not_configured", None
    return "unknown", None


def check_processor() -> tuple[str, str | None]:
    """Check processor health via heartbeat file."""
    # TODO: Check heartbeat file at /tmp/airecruiter_heartbeat
    return "unknown", None


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check(
    db: Session = Depends(get_db),
) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns overall status and component health.
    """
    db_status, _ = check_database(db)
    workday_status, _ = check_workday()
    processor_status, _ = check_processor()

    # Determine overall status
    if db_status == "connected":
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status,
        workday=workday_status,
        processor=processor_status,
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    db: Session = Depends(get_db),
) -> DetailedHealthResponse:
    """
    Detailed health check with component diagnostics.

    Includes error messages for failed components.
    """
    db_status, db_error = check_database(db)
    workday_status, workday_error = check_workday()
    processor_status, processor_error = check_processor()

    # Determine overall status
    if db_status == "connected":
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"

    components = {
        "database": {
            "status": db_status,
            "error": db_error,
            "url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured",
        },
        "workday": {
            "status": workday_status,
            "error": workday_error,
            "tenant_url": settings.WORKDAY_TENANT_URL or "not_configured",
        },
        "processor": {
            "status": processor_status,
            "error": processor_error,
        },
        "s3": {
            "bucket": settings.S3_BUCKET,
            "prefix": settings.S3_PREFIX,
            "region": settings.AWS_REGION,
        },
        "ses": {
            "from_email": settings.SES_FROM_EMAIL,
            "from_name": settings.SES_FROM_NAME,
            "region": settings.SES_REGION,
        },
    }

    return DetailedHealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status,
        workday=workday_status,
        processor=processor_status,
        components=components,
    )


@router.get("/ready")
async def readiness_check(
    db: Session = Depends(get_db),
) -> dict:
    """
    Kubernetes readiness probe.

    Returns 200 if service is ready to accept traffic.
    """
    db_status, _ = check_database(db)

    if db_status != "connected":
        return {"ready": False, "reason": "Database not connected"}

    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe.

    Returns 200 if service process is alive.
    """
    return {"alive": True}
