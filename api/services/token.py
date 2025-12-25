"""HS256 JWT token creation and validation for internal use."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError

from api.config.settings import settings


def create_token(data: dict[str, Any], expires_delta: timedelta = None) -> str:
    """
    Create an HS256-signed JWT token.

    Args:
        data: Claims to include in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    # Set expiration
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate an HS256-signed JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise JWTError("Token has expired")
    except jwt.JWTClaimsError as e:
        raise JWTError(f"Invalid token claims: {e}")
    except JWTError as e:
        raise JWTError(f"Invalid token: {e}")


def should_refresh_token(payload: dict[str, Any]) -> bool:
    """
    Check if token should be refreshed (less than 50% lifetime remaining).

    Args:
        payload: Decoded token payload

    Returns:
        True if token should be refreshed
    """
    exp = payload.get("exp")
    iat = payload.get("iat")

    if not exp or not iat:
        return False

    # Calculate remaining lifetime
    now = datetime.now(timezone.utc).timestamp()
    total_lifetime = exp - iat
    remaining = exp - now

    # Refresh if less than 50% remaining
    return remaining < (total_lifetime * 0.5)


def get_token_expiry(payload: dict[str, Any]) -> datetime | None:
    """Get token expiration as datetime."""
    exp = payload.get("exp")
    if exp:
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    return None
