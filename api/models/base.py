"""Base model with common fields and utilities."""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declared_attr

from api.config.database import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    @declared_attr
    def created_at(cls):
        return Column(
            DateTime,
            default=func.getutcdate(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            onupdate=func.getutcdate(),
            nullable=True,
        )


class BaseModel(Base, TimestampMixin):
    """
    Abstract base class for all models.

    Provides:
    - created_at: Timestamp when record was created
    - updated_at: Timestamp when record was last updated
    - to_dict(): Convert model to dictionary
    """

    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """String representation of model."""
        pk = getattr(self, "id", None)
        return f"<{self.__class__.__name__}(id={pk})>"
