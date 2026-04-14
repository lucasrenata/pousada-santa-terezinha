"""Rotas de gerenciamento de perfil do usuário."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """
    Retorna o perfil do usuário atual com o plano ativo.
    """
    from app.models.enrollment import Enrollment
    from sqlalchemy import select

    # Busca a matrícula ativa mais recente
    stmt = (
        select(Enrollment)
        .where(Enrollment.user_id == current_user.id, Enrollment.status == "ACTIVE")
        .order_by(Enrollment.created_at.desc())
        .limit(1)
    )
    active_enrollment = await db.scalar(stmt)
    
    user_out = UserOut.model_validate(current_user)
    user_out.plan_tier = active_enrollment.plan_tier if active_enrollment else "FREE"
    user_out.has_ai_api_key = bool(current_user.ai_api_key)
    return user_out


@router.put("/me", response_model=UserOut)
async def update_user_me(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserOut:
    """
    Atualiza o perfil do usuário atual.
    """
    if user_in.email is not None:
        current_user.email = str(user_in.email)
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.password is not None:
        current_user.hashed_password = get_password_hash(user_in.password)
    
    # AI Preferences
    if user_in.ai_provider is not None:
        current_user.ai_provider = user_in.ai_provider
    if user_in.ai_model is not None:
        current_user.ai_model = user_in.ai_model
    if user_in.ai_api_key is not None:
        current_user.ai_api_key = user_in.ai_api_key

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    user_out = UserOut.model_validate(current_user)
    user_out.has_ai_api_key = bool(current_user.ai_api_key)
    return user_out
