"""Pydantic schemas for Persona endpoints."""

from datetime import datetime
from typing import Optional

from .base import CamelModel


class PersonaBase(CamelModel):
    """Base persona fields."""

    name: str
    description: Optional[str] = None
    system_prompt_template: str


class PersonaCreate(PersonaBase):
    """Schema for creating a persona."""

    is_default: bool = False


class PersonaUpdate(CamelModel):
    """Schema for updating a persona (all fields optional)."""

    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt_template: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class PersonaResponse(PersonaBase):
    """Schema for persona response."""

    id: int
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class PersonaListItem(CamelModel):
    """Schema for persona in list response."""

    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    is_default: bool
    created_at: datetime
