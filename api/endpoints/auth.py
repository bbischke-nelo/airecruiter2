"""Authentication endpoints for SSO integration."""

from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.config.settings import settings
from api.services.token import create_token
from api.services.sso_token import validate_sso_token, extract_user_info
from api.services.rbac import get_current_user

logger = structlog.get_logger()
router = APIRouter()


class SSOCallbackRequest(BaseModel):
    """Request body for SSO callback."""
    code: str


class UserResponse(BaseModel):
    """User profile response."""
    sub: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    accessible_apps: list[str] = []


class TokenResponse(BaseModel):
    """Token exchange response."""
    user: UserResponse
    expires_in: int


@router.get("/login")
async def login(
    return_url: str = Query(default="/", description="URL to redirect after login"),
) -> RedirectResponse:
    """
    Initiate SSO login flow.

    Redirects to centralized-auth for authentication.
    """
    # Build centralized-auth login URL
    params = {
        "app": settings.SSO_APP_ID,
        "return_url": f"{settings.FRONTEND_URL}/auth/callback?return_url={return_url}",
    }
    sso_login_url = f"{settings.SSO_URL}/api/auth/login?{urlencode(params)}"

    logger.info("Redirecting to SSO login", return_url=return_url)
    return RedirectResponse(url=sso_login_url)


@router.post("/callback", response_model=TokenResponse)
async def sso_callback(
    request: SSOCallbackRequest,
    response: Response,
) -> TokenResponse:
    """
    Exchange SSO auth code for internal token.

    Called by frontend after redirect from centralized-auth.
    """
    try:
        # Exchange auth code with centralized-auth
        logger.info(
            "Exchanging auth code",
            sso_url=settings.SSO_URL,
            code_prefix=request.code[:20] if request.code else "none",
        )
        async with httpx.AsyncClient() as client:
            # Don't send app - centralized-auth gets it from the auth code data
            exchange_response = await client.post(
                f"{settings.SSO_URL}/api/sso/exchange-token",
                json={
                    "auth_code": request.code,
                },
                timeout=10.0,
            )

            if exchange_response.status_code != 200:
                logger.warning(
                    "SSO token exchange failed",
                    status=exchange_response.status_code,
                    body=exchange_response.text,
                )
                raise HTTPException(
                    status_code=401,
                    detail="Failed to exchange auth code",
                )

            data = exchange_response.json()
            sso_token = data.get("token")

            if not sso_token:
                raise HTTPException(
                    status_code=401,
                    detail="No token in SSO response",
                )

    except httpx.RequestError as e:
        logger.error("SSO request failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="SSO service unavailable",
        )

    # Validate SSO token (RS256)
    try:
        sso_payload = validate_sso_token(sso_token)
    except Exception as e:
        logger.warning("SSO token validation failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid SSO token")

    # Extract user info and create internal token
    user_info = extract_user_info(sso_payload)
    internal_token = create_token(user_info)

    # Set cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=internal_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",  # Available for all paths
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    logger.info(
        "SSO login successful",
        user=user_info.get("sub"),
        email=user_info.get("email"),
    )

    return TokenResponse(
        user=UserResponse(**user_info),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.api_route("/logout", methods=["GET", "POST"])
async def logout(response: Response) -> RedirectResponse:
    """
    Logout user by clearing the auth cookie and redirect to login.
    """
    redirect = RedirectResponse(url="/recruiter2/login", status_code=302)
    redirect.delete_cookie(
        key=settings.COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
    )

    logger.info("User logged out")
    return redirect


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user profile.
    """
    return UserResponse(
        sub=user.get("sub", ""),
        email=user.get("email"),
        name=user.get("name"),
        roles=user.get("roles", []),
        accessible_apps=user.get("accessible_apps", []),
    )


@router.post("/refresh")
async def refresh_token(
    response: Response,
    user: dict = Depends(get_current_user),
) -> TokenResponse:
    """
    Refresh the current token.

    Creates a new token with extended expiration.
    """
    # Create new token with same user info
    new_token = create_token({
        "sub": user.get("sub"),
        "email": user.get("email"),
        "name": user.get("name"),
        "roles": user.get("roles", []),
        "accessible_apps": user.get("accessible_apps", []),
        "sso": user.get("sso", True),
    })

    # Set cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=new_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    logger.debug("Token refreshed", user=user.get("sub"))

    return TokenResponse(
        user=UserResponse(
            sub=user.get("sub", ""),
            email=user.get("email"),
            name=user.get("name"),
            roles=user.get("roles", []),
            accessible_apps=user.get("accessible_apps", []),
        ),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
