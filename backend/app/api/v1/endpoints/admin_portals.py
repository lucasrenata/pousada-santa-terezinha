"""Endpoints administrativos para gestão do conteúdo da PortalsSection."""

import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from app.api.deps import get_db, get_current_admin_user
from app.models.portal import PortalSlide, PortalVideo
from app.schemas.portal import (
    PortalSlideCreate,
    PortalSlideUpdate,
    PortalSlideOut,
    PortalVideoCreate,
    PortalVideoOut
)

router = APIRouter()


# ── SLIDES ──────────────────────────────────────────────────────────────────

@router.get("/slides", response_model=List[PortalSlideOut])
async def list_slides(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Lista todos os slides cadastrados."""
    result = await db.execute(select(PortalSlide).order_by(PortalSlide.order.asc()))
    return result.scalars().all()


@router.post("/slides", response_model=PortalSlideOut, status_code=status.HTTP_201_CREATED)
async def create_slide(
    slide_in: PortalSlideCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Cria um novo slide."""
    new_slide = PortalSlide(**slide_in.model_dump())
    db.add(new_slide)
    await db.commit()
    await db.refresh(new_slide)
    return new_slide


@router.put("/slides/{slide_id}", response_model=PortalSlideOut)
async def update_slide(
    slide_id: uuid.UUID,
    slide_in: PortalSlideUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Atualiza um slide existente."""
    result = await db.execute(select(PortalSlide).where(PortalSlide.id == slide_id))
    slide = result.scalar_one_or_none()
    
    if not slide:
        raise HTTPException(status_code=404, detail="Slide não encontrado")
    
    update_data = slide_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(slide, key, value)
    
    await db.commit()
    await db.refresh(slide)
    return slide


@router.delete("/slides/{slide_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slide(
    slide_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Deleta um slide."""
    result = await db.execute(select(PortalSlide).where(PortalSlide.id == slide_id))
    slide = result.scalar_one_or_none()
    
    if not slide:
        raise HTTPException(status_code=404, detail="Slide não encontrado")
    
    await db.delete(slide)
    await db.commit()
    return None


# ── VÍDEO ───────────────────────────────────────────────────────────────────

@router.get("/video", response_model=Optional[PortalVideoOut])
async def get_active_video(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Pega o vídeo atual (assume que existe apenas um ativo ou pega o último)."""
    result = await db.execute(select(PortalVideo).where(PortalVideo.is_active == True).limit(1))
    video = result.scalar_one_or_none()
    
    return video


@router.put("/video", response_model=PortalVideoOut)
async def upsert_video(
    video_in: PortalVideoCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """Atualiza o vídeo atual ou cria um se não existir."""
    # Desativa vídeos anteriores (mantendo apenas 1 oficial)
    await db.execute(update(PortalVideo).values(is_active=False))
    
    new_video = PortalVideo(**video_in.model_dump())
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)
    return new_video
