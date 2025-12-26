"""Security middleware implementing rate limiting and malicious request detection.

Implements security controls per SECURITY_STANDARDS.md:
- Rate limiting (P1)
- Strike system for malicious requests (P1)
- Security headers (P2)
"""

import re
import time
import ipaddress
from typing import Optional, Dict
from collections import defaultdict
from functools import lru_cache

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from api.config.settings import settings

logger = structlog.get_logger()

# Max payload size to scan for malicious content (prevent ReDoS)
MAX_SCAN_SIZE = 4096

# Max body size to read for security scanning (1MB)
# Larger payloads are skipped (rely on upstream validation)
MAX_BODY_SIZE_TO_SCAN = 1 * 1024 * 1024

# Trusted proxy networks (configure based on your infrastructure)
TRUSTED_PROXIES = [
    ipaddress.ip_network("127.0.0.1/32"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

# Compiled regex patterns for attack detection
STRICT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'\.\\./',                        # Path Traversal
    r'%00|\\x00',                     # Null Byte Injection
    r'(?:\||&&)\s*\w',                # Shell Chaining
    r'\$\(\s*\w+\s*\)',               # Shell Command Substitution
    r'<!ENTITY',                      # XML External Entity (XXE)
    r'\bunion\s+select\b',            # SQLi - Union
    r"'\s+OR\s+'1'='1",               # SQLi - Tautology
    r';\s*DROP\s+TABLE',              # SQLi - Destructive
]]

RECON_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'wp-admin|phpmyadmin|\.env',     # Recon probing
    r'\.git/',                        # Git exposure
    r'\.aws/',                        # AWS creds
]]

BODY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'<script\b[^>]*>',               # XSS - Script tag
    r'javascript:\s*[^\s]',           # XSS - JS protocol
    r'on(?:load|click|error|mouse\w+|key\w+)\s*=\s*["\']',  # XSS - Event handlers
]]


class InMemoryRateLimiter:
    """Simple in-memory rate limiter.

    For production, consider Redis-based rate limiting.
    Note: This is per-process and won't work correctly with multiple
    workers or containers. Use Redis for distributed rate limiting.
    """

    # Max age for stale entries (1 hour)
    STALE_ENTRY_AGE = 3600
    # Cleanup interval (every 100 requests)
    CLEANUP_INTERVAL = 100

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._strikes: Dict[str, dict] = {}
        self._request_count = 0

    def _cleanup_old_requests(self, key: str, window_seconds: int) -> None:
        """Remove requests older than the window."""
        cutoff = time.time() - window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def _periodic_cleanup(self) -> None:
        """Periodically clean up stale entries to prevent memory leaks."""
        self._request_count += 1
        if self._request_count < self.CLEANUP_INTERVAL:
            return

        self._request_count = 0
        now = time.time()
        cutoff = now - self.STALE_ENTRY_AGE

        # Clean up old request entries
        stale_keys = [
            key for key, timestamps in self._requests.items()
            if not timestamps or max(timestamps) < cutoff
        ]
        for key in stale_keys:
            del self._requests[key]

        # Clean up old strike entries
        stale_strikes = [
            identity for identity, data in self._strikes.items()
            if data.get("updated_at", 0) < cutoff
        ]
        for identity in stale_strikes:
            del self._strikes[identity]

    def is_rate_limited(self, key: str, limit: int, window: int = 60) -> bool:
        """Check if the key has exceeded the rate limit.

        Args:
            key: Identity key (user:id or ip:address)
            limit: Max requests allowed
            window: Window in seconds

        Returns:
            True if rate limited
        """
        # Run periodic cleanup to prevent memory leaks
        self._periodic_cleanup()

        now = time.time()
        self._cleanup_old_requests(key, window)

        if len(self._requests[key]) >= limit:
            return True

        self._requests[key].append(now)
        return False

    def get_strikes(self, identity: str) -> int:
        """Get strike count for an identity."""
        strike_data = self._strikes.get(identity)
        if not strike_data:
            return 0

        # Check if strikes have decayed (1 hour)
        if time.time() - strike_data.get("updated_at", 0) > 3600:
            del self._strikes[identity]
            return 0

        return strike_data.get("count", 0)

    def add_strike(self, identity: str, severity: int = 1) -> int:
        """Add strikes to an identity.

        Returns:
            New strike count
        """
        now = time.time()

        if identity not in self._strikes:
            self._strikes[identity] = {"count": 0, "updated_at": now}

        # Check for decay
        if now - self._strikes[identity]["updated_at"] > 3600:
            self._strikes[identity] = {"count": 0, "updated_at": now}

        self._strikes[identity]["count"] += severity
        self._strikes[identity]["updated_at"] = now

        return self._strikes[identity]["count"]

    def is_blocked(self, identity: str) -> bool:
        """Check if identity is blocked (3+ strikes)."""
        return self.get_strikes(identity) >= 3


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


def is_trusted_proxy(ip: str) -> bool:
    """Check if IP is a trusted proxy."""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in TRUSTED_PROXIES)
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """Safely determine client IP based on trusted proxy configuration.

    When behind a load balancer (like AWS ALB), we need to read from the
    rightmost untrusted IP in X-Forwarded-For to prevent IP spoofing.
    The load balancer appends the real client IP, so we walk backwards
    through the chain until we find an IP not in our trusted proxies.
    """
    client_host = request.client.host if request.client else "unknown"

    if is_trusted_proxy(client_host):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Parse IPs from X-Forwarded-For (comma-separated)
            ips = [ip.strip() for ip in forwarded.split(",")]

            # Walk backwards to find first untrusted IP
            # This prevents attackers from spoofing by prepending fake IPs
            for ip in reversed(ips):
                if ip and not is_trusted_proxy(ip):
                    return ip

            # All IPs are trusted proxies, fall back to first
            if ips and ips[0]:
                return ips[0]

    return client_host


def get_identity(request: Request) -> str:
    """Get identity for rate limiting.

    Uses user ID if authenticated, otherwise IP.
    """
    # Check for user in request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and user.get("sub"):
        return f"user:{user['sub']}"

    return f"ip:{get_client_ip(request)}"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for rate limiting and attack detection."""

    async def dispatch(self, request: Request, call_next) -> Response:
        identity = get_identity(request)

        # Check if blocked
        if rate_limiter.is_blocked(identity):
            logger.warning("Blocked request from blocked identity", identity=identity)
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

        # Rate limiting
        if await self._check_rate_limit(request, identity):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
            )

        # Check for malicious patterns
        if await self._check_malicious_request(request, identity):
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid request"},
            )

        # Process request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(response)

        return response

    async def _check_rate_limit(self, request: Request, identity: str) -> bool:
        """Check rate limits based on endpoint type."""
        path = request.url.path

        # Auth endpoints - strict limits
        if "/auth/" in path:
            return rate_limiter.is_rate_limited(f"{identity}:auth", limit=10, window=60)

        # Public endpoints - moderate limits
        if "/public/" in path:
            return rate_limiter.is_rate_limited(f"{identity}:public", limit=60, window=60)

        # Authenticated API - generous limits
        return rate_limiter.is_rate_limited(f"{identity}:api", limit=300, window=60)

    async def _check_malicious_request(self, request: Request, identity: str) -> bool:
        """Check for malicious patterns in request."""
        # Build scannable text from URL and headers
        request_data = f"{request.url.path} {request.url.query}"
        headers = " ".join([
            v for k, v in request.headers.items()
            if k.lower() not in ["cookie", "authorization"]
        ])

        scan_text = request_data + " " + headers

        # Check for recon patterns (log only)
        if any(p.search(scan_text) for p in RECON_PATTERNS):
            logger.warning("Reconnaissance detected", identity=identity, path=request.url.path)

        # Check for strict patterns (strike)
        if any(p.search(scan_text) for p in STRICT_PATTERNS):
            strikes = rate_limiter.add_strike(identity)
            logger.warning(
                "Attack pattern detected",
                identity=identity,
                strikes=strikes,
                path=request.url.path,
            )
            return True

        # Check body for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            # Skip JSON (XSS in JSON is a client issue)
            if "application/json" not in content_type:
                # Check Content-Length before reading to prevent DoS
                content_length_str = request.headers.get("content-length", "0")
                try:
                    content_length = int(content_length_str)
                except ValueError:
                    content_length = 0

                # Skip scanning if body is too large (file uploads, etc.)
                # These should be validated by the endpoint handler
                if 0 < content_length <= MAX_BODY_SIZE_TO_SCAN:
                    try:
                        body = await request.body()
                        # Restore body for downstream handlers
                        async def receive():
                            return {"type": "http.request", "body": body, "more_body": False}
                        request._receive = receive

                        # Scan limited portion
                        body_text = body[:MAX_SCAN_SIZE].decode("utf-8", errors="ignore")

                        if any(p.search(body_text) for p in BODY_PATTERNS):
                            strikes = rate_limiter.add_strike(identity)
                            logger.warning(
                                "XSS pattern in body",
                                identity=identity,
                                strikes=strikes,
                            )
                            return True
                    except Exception:
                        pass  # If we can't read body, let it through

        return False

    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        # HSTS - only in production
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP - adjust based on your needs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
