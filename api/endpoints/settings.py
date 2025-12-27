"""System settings endpoints."""

import asyncio
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import Setting, DEFAULT_SETTINGS
from api.schemas.settings import SettingsResponse, SettingsUpdate
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


class DispositionOption(BaseModel):
    """A disposition option from Workday."""
    id: str
    name: str
    workday_id: str | None = None


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Get a setting value from database."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        return setting.value
    return DEFAULT_SETTINGS.get(key, (default, ""))[0]


def set_setting_value(db: Session, key: str, value: str) -> None:
    """Set a setting value in database."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        description = DEFAULT_SETTINGS.get(key, ("", ""))[1]
        setting = Setting(key=key, value=value, description=description)
        db.add(setting)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Get all system settings."""
    return SettingsResponse(
        # Email settings
        email_from_address=get_setting_value(db, "email_from_address", "jobs@ccfs.com"),
        email_from_name=get_setting_value(db, "email_from_name", "CCFS Talent Team"),
        # Interview settings
        interview_token_expiry_days=int(get_setting_value(db, "interview_token_expiry_days", "7")),
        # Global requisition defaults
        auto_send_interview_default=get_setting_value(db, "auto_send_interview_default", "false").lower() == "true",
        advance_stage_id=get_setting_value(db, "advance_stage_id", "") or None,
        reject_disposition_id=get_setting_value(db, "reject_disposition_id", "") or None,
        # Legacy
        default_recruiter_id=int(v) if (v := get_setting_value(db, "default_recruiter_id", "")) and v.isdigit() else None,
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update system settings."""
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if value is not None:
            set_setting_value(db, key, str(value))

    db.commit()

    logger.info("Settings updated", keys=list(update_data.keys()))
    return await get_settings(db, user)


@router.post("/seed")
async def seed_settings(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Seed default settings if not present."""
    for setting_key, (value, description) in DEFAULT_SETTINGS.items():
        existing = db.query(Setting).filter(Setting.key == setting_key).first()
        if not existing:
            setting = Setting(key=setting_key, value=value, description=description)
            db.add(setting)

    db.commit()
    logger.info("Settings seeded")
    return {"message": "Settings seeded successfully"}


@router.get("/dispositions", response_model=List[DispositionOption])
async def get_dispositions(
    user: dict = Depends(require_role(["admin", "recruiter"])),
):
    """Fetch available disposition options from Workday.

    These are the valid rejection reasons that can be used when rejecting
    a candidate. The values come directly from your Workday configuration.
    """
    try:
        # Import here to avoid circular imports and only when needed
        from processor.tms.providers.workday.provider import WorkdayProvider
        from processor.tms.providers.workday.config import WorkdayConfig
        from api.config.settings import settings

        # Create provider with config from environment
        config = WorkdayConfig(
            tenant_url=settings.WORKDAY_TENANT_URL,
            tenant_id=settings.WORKDAY_TENANT_ID,
            client_id=settings.WORKDAY_CLIENT_ID,
            client_secret=settings.WORKDAY_CLIENT_SECRET,
            refresh_token=settings.WORKDAY_REFRESH_TOKEN,
            api_version=settings.WORKDAY_API_VERSION,
        )
        provider = WorkdayProvider(config)
        await provider.initialize()

        dispositions = await provider.get_dispositions()

        return [
            DispositionOption(
                id=d.get("id") or d.get("name", ""),
                name=d.get("name", ""),
                workday_id=d.get("workday_id"),
            )
            for d in dispositions
            if d.get("id") or d.get("name")
        ]

    except Exception as e:
        logger.error("Failed to fetch dispositions from Workday", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch dispositions from Workday: {str(e)}"
        )
