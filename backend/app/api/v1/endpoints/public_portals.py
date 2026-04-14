"""Endpoints públicos para o conteúdo da PortalsSection."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db
from app.models.portal import PortalSlide, PortalVideo
from app.schemas.portal import PortalContentOut

router = APIRouter()


@router.get("/content", response_model=PortalContentOut)
async def get_portal_content(db: AsyncSession = Depends(get_db)):
    """Retorna o conteúdo consolidado para a PortalsSection."""
    
    # Busca slides ativos e ordenados
    slides_result = await db.execute(
        select(PortalSlide)
        .where(PortalSlide.is_active == True)
        .order_by(PortalSlide.order.asc())
    )
    slides = slides_result.scalars().all()
    
    # Separa por posição
    left_slides = [s for s in slides if s.position == 'left']
    right_slides = [s for s in slides if s.position == 'right']
    
    # Busca vídeo ativo
    video_result = await db.execute(
        select(PortalVideo)
        .where(PortalVideo.is_active == True)
        .limit(1)
    )
    video = video_result.scalar_one_or_none()
    
    return {
        "left_slides": left_slides,
        "right_slides": right_slides,
        "video": video
    }
