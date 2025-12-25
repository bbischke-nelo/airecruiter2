"""Base Pydantic schemas with CamelCase conversion."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from humps import camelize


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    return camelize(string)


class CamelModel(BaseModel):
    """
    Base model that converts snake_case fields to camelCase in JSON responses.

    Usage:
        class MyResponse(CamelModel):
            external_application_id: str  # JSON: externalApplicationId
            candidate_name: str           # JSON: candidateName
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


T = TypeVar("T")


class PaginationMeta(CamelModel):
    """Pagination metadata."""

    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(CamelModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Usage:
        PaginatedResponse[RequisitionResponse](
            data=[...],
            meta=PaginationMeta(page=1, per_page=20, total=100, total_pages=5)
        )
    """

    data: list[T]
    meta: PaginationMeta


class ErrorDetail(CamelModel):
    """Error detail for API error responses."""

    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(CamelModel):
    """Standard error response format."""

    error: ErrorDetail
