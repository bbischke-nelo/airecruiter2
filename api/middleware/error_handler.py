"""Global exception handlers for the API."""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

logger = structlog.get_logger()


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        status_code: int = 400,
        details: dict = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str | int):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": identifier},
        )


class ValidationAPIError(APIError):
    """Validation error."""

    def __init__(self, message: str, field: str = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={"field": field} if field else {},
        )


class ForbiddenError(APIError):
    """Access forbidden."""

    def __init__(self, message: str = "You don't have permission to access this resource"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Handle custom API errors."""
        logger.warning(
            "API error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Validation error")

        logger.warning(
            "Validation error",
            field=field,
            message=message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                    "details": {"field": field, "errors": errors},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Handle database errors."""
        logger.error(
            "Database error",
            error=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "A database error occurred",
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(
            "Unexpected error",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )
