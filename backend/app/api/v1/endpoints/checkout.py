"""Endpoints de checkout: matrícula inicial e upgrade de plano."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentCreate
from app.services.mercadopago_service import (
    PLAN_HIERARCHY,
    PLAN_PRICES,
    create_preference,
    create_upgrade_preference,
    generate_payment_link,
)

router = APIRouter()

class PublicCheckoutRequest(BaseModel):
    email: str
    password: str
    fullname: str
    phone: str
    plan_tier: str

@router.post("/public/checkout", status_code=status.HTTP_200_OK)
async def public_checkout(
    payload: PublicCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    # 1. Busca do Usuário
    stmt = select(User).where(User.email == payload.email)
    user = await db.scalar(stmt)

    if not user:
        # 2. Se o Usuário NÃO existir:
        hashed_password = get_password_hash(payload.password)
        user = User(
            email=payload.email,
            hashed_password=hashed_password,
            full_name=payload.fullname,
            role=UserRole.STUDENT,
        )
        db.add(user)
        await db.flush()  # Para pegar o user.id

        new_enrollment = Enrollment(
            user_id=user.id,
            plan_tier=payload.plan_tier.upper(),
            status="PENDING"
        )
        db.add(new_enrollment)
        await db.commit()
    else:
        # 3. Se o Usuário JÁ existir (Autenticação Silenciosa):
        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="E-mail já cadastrado com outra senha. Faça login ou recupere sua senha.")

        # 4. Verificação de Matrícula (Para usuários existentes validados):
        enrollment_stmt = select(Enrollment).where(
            Enrollment.user_id == user.id
        ).order_by(Enrollment.created_at.desc())
        
        enrollments = await db.scalars(enrollment_stmt)
        existing_enrollment = enrollments.first()
        
        if existing_enrollment and existing_enrollment.status == "ACTIVE":
            raise HTTPException(status_code=400, detail="Você já possui uma assinatura ativa. Faça login para acessar a plataforma.")
            
        if existing_enrollment and existing_enrollment.status in ["PENDING", "CANCELLED", "EXPIRED"]:
            existing_enrollment.plan_tier = payload.plan_tier.upper()
            existing_enrollment.status = "PENDING"
            await db.commit()
        elif not existing_enrollment:
             # Isso não deve acontecer normalmente se ele passou pelo checkout de cima e deu erro, mas como segurança criamos um.
             new_enrollment = Enrollment(
                 user_id=user.id,
                 plan_tier=payload.plan_tier.upper(),
                 status="PENDING"
             )
             db.add(new_enrollment)
             await db.commit()

    # 5. Geração do Link (Comum para novos e existentes PENDING):
    init_point = await generate_payment_link(str(user.id), user.email, payload.plan_tier.upper())
    
    return {
        "status": "success",
        "init_point": init_point,
        "user_id": str(user.id)
    }

# ── POST /checkout/retry-payment (usuário logado) ──────────────────────────

@router.post("/retry-payment", status_code=status.HTTP_200_OK)
async def retry_payment(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gera um novo link de pagamento para um usuário já logado que possui
    uma matrícula pendente, cancelada ou expirada.
    """
    stmt = (
        select(Enrollment)
        .where(Enrollment.user_id == current_user.id)
        .order_by(Enrollment.created_at.desc())
    )
    enrollment = await db.scalar(stmt)

    if not enrollment:
        raise HTTPException(
            status_code=400, 
            detail="Nenhuma matrícula encontrada para este usuário."
        )

    if enrollment.status == "ACTIVE":
        raise HTTPException(
            status_code=400, 
            detail="Você já possui uma assinatura ativa."
        )

    # Gera novo link usando o plan_tier atual da matrícula
    try:
        init_point = await generate_payment_link(
            str(current_user.id), 
            current_user.email, 
            enrollment.plan_tier.upper()
        )
        return {
            "status": "success",
            "init_point": init_point
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar novo link de pagamento: {str(e)}"
        )


# ── POST /checkout/preferences (matrícula inicial) ─────────────────────────

@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_checkout_preference(
    payload: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    enrollment = Enrollment(
        user_id=current_user.id,
        plan_tier=payload.plan_tier.upper(),
        status="PENDING",
        expires_at=None,
    )
    db.add(enrollment)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar matrícula",
        ) from exc

    try:
        init_point = await create_preference(current_user, payload.plan_tier)
        return {"init_point": init_point}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar preferência de pagamento",
        ) from exc


# ── POST /checkout/upgrade ─────────────────────────────────────────────────

class UpgradeRequest(BaseModel):
    target_tier: str


@router.post("/upgrade", status_code=status.HTTP_201_CREATED)
async def create_upgrade(
    payload: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Cobra apenas a DIFERENÇA de preço entre o plano atual e o alvo.
    Não permite downgrade (retorna 400).
    """
    target_tier = payload.target_tier.upper()

    # Valida se o tier alvo é reconhecido
    if target_tier not in PLAN_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plano inválido: {target_tier}. Opções: {list(PLAN_PRICES)}",
        )

    # Busca enrollment ativo
    now = datetime.now(timezone.utc)
    enrollment = await db.scalar(
        select(Enrollment)
        .where(
            Enrollment.user_id == current_user.id,
            Enrollment.status == "ACTIVE",
            (Enrollment.expires_at.is_(None) | (Enrollment.expires_at > now)),
        )
        .order_by(Enrollment.created_at.desc())
    )

    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma matrícula ativa encontrada. Faça a matrícula inicial primeiro.",
        )

    current_tier = enrollment.plan_tier.upper()

    # Valida que é realmente um upgrade (não downgrade ou mesmo tier)
    try:
        current_idx = PLAN_HIERARCHY.index(current_tier)
        target_idx = PLAN_HIERARCHY.index(target_tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier inválido na hierarquia de planos.",
        )

    if target_idx <= current_idx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Downgrade não permitido. Plano atual: {current_tier}, "
                f"solicitado: {target_tier}."
            ),
        )

    # Calcula a diferença justa
    diff_price = round(PLAN_PRICES[target_tier] - PLAN_PRICES[current_tier], 2)

    try:
        init_point = await create_upgrade_preference(current_user, target_tier, diff_price)
        return {"init_point": init_point, "diff_price": str(diff_price)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar preferência de upgrade",
        ) from exc
