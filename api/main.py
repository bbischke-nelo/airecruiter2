"""
AIRecruiter v2 API - FastAPI Application

Main entry point for the API server.
Run with: uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config.settings import settings
from api.config.database import init_db
from api.endpoints import api_router
from api.endpoints.interview_websocket import router as ws_router
from api.middleware.auth import AuthMiddleware
from api.middleware.error_handler import setup_exception_handlers
from api.middleware.logging import LoggingMiddleware, configure_logging
from api.middleware.security import SecurityMiddleware
from api.services.encryption import validate_encryption_key

# Configure structured logging
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info(
        "Starting AIRecruiter v2 API",
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    # Validate encryption key (fails fast in production if missing)
    try:
        validate_encryption_key()
        logger.info("Encryption key validated")
    except Exception as e:
        logger.critical("Encryption key validation failed", error=str(e))
        raise  # Prevent app from starting

    # Initialize database tables (in dev mode)
    if settings.DEBUG:
        logger.info("Initializing database tables (DEBUG mode)")
        try:
            init_db()
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down AIRecruiter v2 API")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered candidate screening and interview system",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Setup exception handlers
setup_exception_handlers(app)

# Add CORS middleware (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware (rate limiting, attack detection)
app.add_middleware(SecurityMiddleware)

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Add logging middleware (innermost - logs after auth)
app.add_middleware(LoggingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Include WebSocket routes (no auth middleware for WebSocket)
app.include_router(ws_router, prefix="/api/v1")


# Root health endpoint (for ALB)
@app.get("/health")
async def root_health():
    """Simple health check for load balancer."""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs" if settings.DEBUG else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
