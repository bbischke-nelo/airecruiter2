"""RS256 SSO token validation for centralized-auth integration."""

from pathlib import Path
from typing import Any

from jose import jwt, JWTError
import structlog

from api.config.settings import settings

logger = structlog.get_logger()

# Cache for public key
_public_key_cache: str | None = None


def load_public_key() -> str | None:
    """Load RS256 public key from file."""
    global _public_key_cache

    if _public_key_cache:
        return _public_key_cache

    if not settings.SSO_PUBLIC_KEY_PATH:
        logger.warning("SSO_PUBLIC_KEY_PATH not configured")
        return None

    key_path = Path(settings.SSO_PUBLIC_KEY_PATH)
    if not key_path.exists():
        logger.error("SSO public key file not found", path=str(key_path))
        return None

    _public_key_cache = key_path.read_text()
    logger.info("Loaded SSO public key", path=str(key_path))
    return _public_key_cache


def validate_sso_token(token: str) -> dict[str, Any]:
    """
    Validate an RS256-signed SSO token from centralized-auth.

    Args:
        token: JWT token string from SSO

    Returns:
        Decoded token payload with user info

    Raises:
        JWTError: If token is invalid or expired
    """
    public_key = load_public_key()

    if not public_key:
        raise JWTError("SSO public key not configured")

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.SSO_APP_ID,
            issuer="centralized-auth",
        )

        # Validate required claims
        required_claims = ["sub", "email", "roles"]
        for claim in required_claims:
            if claim not in payload:
                raise JWTError(f"Missing required claim: {claim}")

        logger.debug(
            "SSO token validated",
            sub=payload.get("sub"),
            email=payload.get("email"),
        )

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("SSO token expired")
        raise JWTError("SSO token has expired")
    except jwt.JWTClaimsError as e:
        logger.warning("SSO token claims invalid", error=str(e))
        raise JWTError(f"Invalid SSO token claims: {e}")
    except JWTError as e:
        logger.warning("SSO token validation failed", error=str(e))
        raise JWTError(f"Invalid SSO token: {e}")


def extract_user_info(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Extract user information from SSO token payload.

    Args:
        payload: Decoded SSO token payload

    Returns:
        User info dict for internal token
    """
    return {
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name"),
        "roles": payload.get("roles", []),
        "accessible_apps": payload.get("accessibleApps", []),
        "sso": True,  # Mark as SSO-authenticated
    }
