"""Schemas para conteúdo dos portais (Slides e Vídeos)."""

import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ── SLIDES ──────────────────────────────────────────────────────────────────

class PortalSlideBase(BaseModel):
    position: str  # 'left' ou 'right'
    image_url: str
    order: int = 0
    is_active: bool = True


class PortalSlideCreate(PortalSlideBase):
    pass


class PortalSlideUpdate(BaseModel):
    position: Optional[str] = None
    image_url: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class PortalSlideOut(PortalSlideBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


# ── VÍDEO ───────────────────────────────────────────────────────────────────

class PortalVideoBase(BaseModel):
    title: str
    description: Optional[str] = None
    video_url: str
    is_active: bool = True


class PortalVideoCreate(PortalVideoBase):
    pass


class PortalVideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    is_active: Optional[bool] = None


class PortalVideoOut(PortalVideoBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


# ── CONTEÚDO PÚBLICO CONSOLIDADO ──────────────────────────────────────────

class PortalContentOut(BaseModel):
    left_slides: List[PortalSlideOut]
    right_slides: List[PortalSlideOut]
    video: Optional[PortalVideoOut] = None
