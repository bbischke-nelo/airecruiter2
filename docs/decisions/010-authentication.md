# ADR 010: Authentication via Centralized-Auth

**Status:** Accepted
**Date:** 2025-01-15

## Context

v1 uses centralized-auth as an SSO hub backed by Azure AD. This works well and should be preserved.

## Decision

v2 will use the **same authentication architecture** as v1:

1. **centralized-auth** handles all SSO (Azure AD integration)
2. **airecruiter2** validates tokens issued by centralized-auth
3. **RBAC** uses existing Azure AD group mappings

## Authentication Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ airecruiter │────▶│ centralized-auth │────▶│  Azure AD   │
│     v2      │     │   (SSO Hub)      │     │             │
└─────────────┘     └──────────────────┘     └─────────────┘
      │                     │
      │  1. Redirect        │  2. Azure AD login
      │◀────────────────────│◀─────────────────────
      │                     │
      │  4. Exchange code   │  3. Return auth code
      │────────────────────▶│
      │                     │
      │  5. JWT token       │
      │◀────────────────────│
```

### Steps

1. User visits airecruiter2, not logged in
2. Redirect to `{CENTRALIZED_AUTH_URL}/auth/login?app=recruiter&return_url=...`
3. centralized-auth redirects to Azure AD
4. User authenticates with Azure AD
5. Azure AD returns auth code to centralized-auth
6. centralized-auth creates auth code, redirects to airecruiter2 callback
7. airecruiter2 exchanges auth code for JWT token
8. JWT stored in HTTP-only cookie (`recruiter_access_token`)

## Token Validation

### SSO Token (from centralized-auth)
- Algorithm: **RS256** (asymmetric)
- Public key: loaded from `SSO_PUBLIC_KEY_PATH`
- Required claims: `exp`, `sub`, `email`, `roles`

### Internal Token (airecruiter2)
- Algorithm: **HS256** (symmetric)
- Secret: `SECRET_KEY` environment variable
- Expiration: 720 minutes (12 hours)
- Rolling refresh: auto-renew when <50% lifetime remaining

## RBAC Roles

Mapped from Azure AD groups:

| Role Group | Azure AD Groups | Access Level |
|------------|-----------------|--------------|
| Admin | `ERP_Admin`, `ERP_IT`, `ERP_DEV` | Full access |
| HR | `ERP_HR`, `ERP_HR_MGR` | Full recruiter access |
| Management | `ERP_*_MGR`, `ERP_*_DIR`, `ERP_*_VP` | Read + limited write |

### Permission Mapping for v2

| Endpoint | Required Role |
|----------|---------------|
| Credentials CRUD | Admin only |
| Settings CRUD | Admin only |
| Prompts/Personas CRUD | Admin only |
| Queue clear/modify | Admin only |
| Requisitions CRUD | Admin, HR |
| Applications read | Admin, HR, Management |
| Interviews read/create | Admin, HR |
| Public interview | No auth (token-based) |

## Configuration

```bash
# centralized-auth integration
SSO_URL=https://auth.company.com
SSO_APP_ID=recruiter
SSO_APP_SECRET=...                    # Shared secret with centralized-auth
SSO_PUBLIC_KEY_PATH=/path/to/public.pem  # RS256 public key

# Internal token signing
SECRET_KEY=...                        # HS256 secret (32+ bytes)
ACCESS_TOKEN_EXPIRE_MINUTES=720

# Cookie settings
COOKIE_DOMAIN=.company.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

## Implementation

### Auth Middleware

```python
# api/middleware/auth.py
SKIP_AUTH_PATHS = [
    "/api/v1/auth/",
    "/api/v1/public/",
    "/health",
]

async def auth_middleware(request: Request, call_next):
    if any(request.url.path.startswith(p) for p in SKIP_AUTH_PATHS):
        return await call_next(request)

    token = request.cookies.get("recruiter_access_token")
    if not token:
        token = get_bearer_token(request)

    if not token:
        raise HTTPException(401, "Not authenticated")

    payload = decode_token(token)
    request.state.user = payload

    response = await call_next(request)

    # Rolling refresh
    if should_refresh(payload):
        new_token = create_token(payload)
        response.set_cookie("recruiter_access_token", new_token, ...)

    return response
```

### SSO Callback Endpoint

```python
# api/endpoints/auth.py
@router.post("/sso/callback")
async def sso_callback(request: SSOCallbackRequest):
    # Exchange auth code with centralized-auth
    response = await http_client.post(
        f"{settings.SSO_URL}/api/sso/exchange-token",
        headers={
            "X-App-Id": settings.SSO_APP_ID,
            "X-App-Secret": settings.SSO_APP_SECRET,
        },
        json={"auth_code": request.code}
    )

    sso_token = response.json()["token"]

    # Validate RS256 signature
    payload = validate_sso_token(sso_token)

    # Create internal HS256 token
    internal_token = create_token({
        "sub": payload["sub"],
        "email": payload["email"],
        "name": payload["name"],
        "roles": payload["roles"],
        "sso": True,
    })

    response = JSONResponse({"user": payload})
    response.set_cookie("recruiter_access_token", internal_token, ...)
    return response
```

## Consequences

### Positive

1. **No new auth system**: Reuse proven centralized-auth
2. **SSO continuity**: Users already authenticated
3. **Consistent RBAC**: Same roles across all apps
4. **Security**: RS256 for SSO, rate limiting, strike-based blocking in centralized-auth

### Negative

1. **Dependency**: centralized-auth must be available
2. **Key management**: Must keep RSA public key in sync

## Files to Implement

```
api/
├── endpoints/auth.py           # Login, logout, SSO callback
├── middleware/auth.py          # Token validation middleware
├── services/
│   ├── token.py               # HS256 token creation/validation
│   ├── sso_token.py           # RS256 SSO token validation
│   └── rbac.py                # Role-based access control
└── config/settings.py         # Auth configuration
```
