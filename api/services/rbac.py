"""Role-based access control for API endpoints."""

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request
import structlog

logger = structlog.get_logger()


# Role hierarchy - higher roles include permissions of lower roles
ROLE_HIERARCHY = {
    "admin": ["admin", "recruiter", "readonly"],
    "recruiter": ["recruiter", "readonly"],
    "readonly": ["readonly"],
}

# Map Azure AD groups to internal roles
AD_GROUP_TO_ROLE = {
    "ERP_Admin": "admin",
    "ERP_IT": "admin",
    "ERP_DEV": "admin",
    "ERP_HR": "recruiter",
    "ERP_HR_MGR": "recruiter",
    # Management roles get recruiter access
    "ERP_AP_MGR": "recruiter",
    "ERP_AR_MGR": "recruiter",
    "ERP_CLAIMS_MGR": "recruiter",
    "ERP_COMPLIANCE_MGR": "recruiter",
    "ERP_CS_MGR": "recruiter",
    "ERP_FAC_MGR": "recruiter",
    "ERP_FIN_MGR": "recruiter",
    "ERP_FLEET_MGR": "recruiter",
    "ERP_INTERLINE_MGR": "recruiter",
    "ERP_LH_DIR": "recruiter",
    "ERP_OPS_DIR": "recruiter",
    "ERP_OPS_MGR": "recruiter",
    "ERP_OPS_VP": "recruiter",
    "ERP_OSD_MGR": "recruiter",
    "ERP_PRICING_MGR": "recruiter",
    "ERP_SAFETY_MGR": "recruiter",
    "ERP_SALES_MGR": "recruiter",
}


def get_user_role(roles: list[str]) -> str:
    """
    Get the highest role from a list of Azure AD group names.

    Args:
        roles: List of Azure AD group names from token

    Returns:
        Internal role name (admin, recruiter, or readonly)
    """
    # Check for admin roles first
    for role in roles:
        if role in AD_GROUP_TO_ROLE and AD_GROUP_TO_ROLE[role] == "admin":
            return "admin"

    # Check for recruiter roles
    for role in roles:
        if role in AD_GROUP_TO_ROLE and AD_GROUP_TO_ROLE[role] == "recruiter":
            return "recruiter"

    # Default to readonly
    return "readonly"


def has_role(user_roles: list[str], required_role: str) -> bool:
    """
    Check if user has the required role or higher.

    Args:
        user_roles: List of Azure AD group names from token
        required_role: Required role to check

    Returns:
        True if user has required role or higher
    """
    user_role = get_user_role(user_roles)
    allowed_roles = ROLE_HIERARCHY.get(user_role, [])
    return required_role in allowed_roles


def get_current_user(request: Request) -> dict[str, Any]:
    """
    Get current user from request state.

    Usage:
        @router.get("/me")
        def get_me(user: dict = Depends(get_current_user)):
            return user
    """
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.state.user


def require_role(allowed_roles: list[str]) -> Callable:
    """
    Dependency that requires user to have one of the specified roles.

    Usage:
        @router.post("/admin-only")
        def admin_endpoint(user: dict = Depends(require_role(["admin"]))):
            return {"message": "Admin access granted"}
    """
    def check_role(request: Request) -> dict[str, Any]:
        user = get_current_user(request)
        user_roles = user.get("roles", [])

        for role in allowed_roles:
            if has_role(user_roles, role):
                logger.debug(
                    "Role check passed",
                    user=user.get("sub"),
                    required=allowed_roles,
                    user_role=get_user_role(user_roles),
                )
                return user

        logger.warning(
            "Role check failed",
            user=user.get("sub"),
            required=allowed_roles,
            user_roles=user_roles,
        )
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this resource",
        )

    return check_role


def require_admin(request: Request) -> dict[str, Any]:
    """
    Dependency that requires admin role.

    Usage:
        @router.delete("/dangerous")
        def delete_all(user: dict = Depends(require_admin)):
            ...
    """
    return require_role(["admin"])(request)
