"""Authentication middleware for JWT validation."""

import re
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.config.settings import settings
from api.services.token import decode_token, create_token, should_refresh_token


# Paths that don't require authentication
SKIP_AUTH_PATHS = [
    r"^/api/v1/auth/",
    r"^/api/v1/public/",
    r"^/health",
    r"^/api/docs",
    r"^/api/openapi\.json",
    r"^/api/redoc",
]

SKIP_AUTH_PATTERNS = [re.compile(p) for p in SKIP_AUTH_PATHS]


def should_skip_auth(path: str) -> bool:
    """Check if path should skip authentication."""
    return any(pattern.match(path) for pattern in SKIP_AUTH_PATTERNS)


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from request (cookie or Authorization header)."""
    # Try cookie first
    token = request.cookies.get(settings.COOKIE_NAME)
    if token:
        return token

    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT tokens on protected routes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and validate authentication."""
        # Skip auth for certain paths
        if should_skip_auth(request.url.path):
            return await call_next(request)

        # Get token
        token = get_token_from_request(request)
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Decode and validate token
        try:
            payload = decode_token(token)
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))

        # Store user info in request state
        request.state.user = payload
        request.state.user_id = payload.get("sub")
        request.state.user_email = payload.get("email")
        request.state.user_roles = payload.get("roles", [])

        # Call next middleware/handler
        response = await call_next(request)

        # Rolling token refresh
        if should_refresh_token(payload):
            new_token = create_token(payload)
            response.set_cookie(
                key=settings.COOKIE_NAME,
                value=new_token,
                httponly=True,
                secure=settings.COOKIE_SECURE,
                samesite=settings.COOKIE_SAMESITE,
                domain=settings.COOKIE_DOMAIN,
                max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

        return response
