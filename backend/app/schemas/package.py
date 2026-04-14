"""Schemas de Pacotes (planos de acesso)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PackageBase(BaseModel):
    title: str
    teaser: str | None = None
    price: float
    thumbnail_url: str | None = None
    tier_name: str
    is_active: bool = True


class PackageCreate(PackageBase):
    pass


class PackageUpdate(BaseModel):
    title: str | None = None
    teaser: str | None = None
    price: float | None = None
    thumbnail_url: str | None = None
    tier_name: str | None = None
    is_active: bool | None = None


class PackageOut(PackageBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
