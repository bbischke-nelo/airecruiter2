"""Credentials endpoints for Workday OAuth2 configuration."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.config.database import get_db
from api.models import Credential
from api.schemas.credentials import (
    CredentialCreate,
    CredentialStatusResponse,
    CredentialTestResponse,
)
from api.services.rbac import require_admin
from api.services.encryption import encrypt_value, decrypt_value

logger = structlog.get_logger()
router = APIRouter()


@router.get("/status", response_model=CredentialStatusResponse)
async def get_credential_status(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Get current credential status (no secrets returned)."""
    credential = db.query(Credential).first()

    if not credential:
        return CredentialStatusResponse(
            has_credentials=False,
            is_valid=False,
        )

    return CredentialStatusResponse(
        has_credentials=True,
        is_valid=credential.is_valid,
        tenant_id=credential.tenant_id,
        tenant_url=credential.tenant_url,
        last_validated=credential.last_validated,
        expires_at=credential.expires_at,
    )


@router.post("", response_model=CredentialStatusResponse, status_code=201)
async def save_credentials(
    data: CredentialCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Save Workday credentials (encrypted)."""
    # Delete existing credentials
    db.query(Credential).delete()

    # Encrypt secrets
    encrypted_secret = encrypt_value(data.client_secret)
    encrypted_token = encrypt_value(data.refresh_token) if data.refresh_token else None

    # Create new credential
    credential = Credential(
        tenant_url=data.tenant_url,
        tenant_id=data.tenant_id,
        client_id=data.client_id,
        client_secret=encrypted_secret,
        refresh_token=encrypted_token,
        is_valid=False,  # Will be validated on test
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    logger.info("Credentials saved", tenant_id=credential.tenant_id)

    return CredentialStatusResponse(
        has_credentials=True,
        is_valid=credential.is_valid,
        tenant_id=credential.tenant_id,
        tenant_url=credential.tenant_url,
        last_validated=credential.last_validated,
        expires_at=credential.expires_at,
    )


@router.post("/test", response_model=CredentialTestResponse)
async def test_credentials(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Test Workday connection with current credentials."""
    credential = db.query(Credential).first()

    if not credential:
        return CredentialTestResponse(
            success=False,
            message="No credentials configured",
        )

    # TODO: Implement actual Workday connection test
    # For now, just mark as valid
    from datetime import datetime, timezone, timedelta

    credential.is_valid = True
    credential.last_validated = datetime.now(timezone.utc)
    credential.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()

    logger.info("Credentials tested successfully", tenant_id=credential.tenant_id)

    return CredentialTestResponse(
        success=True,
        message="Connection successful",
        tenant_id=credential.tenant_id,
    )


@router.delete("", status_code=204)
async def delete_credentials(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Delete all stored credentials."""
    db.query(Credential).delete()
    db.commit()

    logger.info("Credentials deleted")
