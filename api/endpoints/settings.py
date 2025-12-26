"""System settings endpoints."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import Setting, DEFAULT_SETTINGS
from api.schemas.settings import SettingsResponse, SettingsUpdate
from api.services.rbac import require_role, require_admin

logger = structlog.get_logger()
router = APIRouter()


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
        email_from_address=get_setting_value(db, "email_from_address", "noreply@company.com"),
        email_from_name=get_setting_value(db, "email_from_name", "AIRecruiter"),
        # Interview settings
        interview_token_expiry_days=int(get_setting_value(db, "interview_token_expiry_days", "7")),
        # Global requisition defaults
        auto_send_interview_default=get_setting_value(db, "auto_send_interview_default", "false").lower() == "true",
        advance_stage_id=get_setting_value(db, "advance_stage_id", "") or None,
        reject_disposition_id=get_setting_value(db, "reject_disposition_id", "") or None,
        # Legacy
        default_recruiter_id=int(get_setting_value(db, "default_recruiter_id", "0")) or None,
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
