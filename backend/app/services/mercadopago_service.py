from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import anyio
import asyncio
import mercadopago
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enrollment import Enrollment
from app.models.payment import Payment
from app.models.user import User

# ── Tabela de preços completos por plan_tier ───────────────────────────────
PLAN_PRICES: dict[str, float] = {
    "MENSAL": 9.90,
    "BASICO": 598.80,
    "PREMIUM": 1078.80,
}

# Duração em dias por tier
PLAN_DURATION_DAYS: dict[str, int] = {
    "MENSAL": 30,
    "BASICO": 365,
    "PREMIUM": 365,
}

PLAN_HIERARCHY = ["MENSAL", "BASICO", "PREMIUM"]

sdk_instance = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

PLANS_CONFIG = {
    "BASICO": {"title": "Plano Básico Anual", "price": 598.80, "installments": 12},
    "PREMIUM": {"title": "Plano Premium Anual", "price": 1078.80, "installments": 12},
    "MENSAL": {"title": "Plano Mensal", "price": 9.90, "installments": 1}
}

async def generate_payment_link(user_id: str, user_email: str, plan_tier: str) -> str:
    plan = PLANS_CONFIG.get(plan_tier)
    if not plan:
        raise HTTPException(status_code=400, detail="Plano inválido para checkout")

    # MP exige que as back_urls sejam enviadas para auto_return
    base_url = settings.NGROK_URL.rstrip("/") if settings.NGROK_URL else settings.FRONTEND_URL.rstrip("/")
    preference_data = {
        "items": [
            {
                "title": plan["title"],
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(plan["price"]) # Ensure float serialization
            }
        ],
        "payer": {
            "email": user_email
        },
        "back_urls": {
            "success": f"{base_url}/dashboard?payment=success",
            "failure": f"{base_url}/dashboard?payment=failure",
            "pending": f"{base_url}/dashboard?payment=pending"
        },
        "auto_return": "approved",
        "notification_url": settings.WEBHOOK_URL,
        "external_reference": str(user_id)
    }

    try:
        response = await asyncio.to_thread(sdk_instance.preference().create, preference_data)
        
        status = response.get("status")
        if status in (200, 201):
            init_point = response.get("response", {}).get("init_point")
            if init_point:
                return init_point
            
        error_msg = response.get("response", {})
        raise HTTPException(
            status_code=500, 
            detail=f"Mercado Pago não retornou init_point validamente. Detalhes: {error_msg}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro Interno Mercado Pago: {str(e)}")



def _plan_index(tier: str) -> int:
    try:
        return PLAN_HIERARCHY.index(tier.upper())
    except ValueError:
        return -1


# ── Preferência de compra inicial ─────────────────────────────────────────

async def create_preference(user: User, plan_tier: str) -> str:
    """Cria a preferência de pagamento inicial para um plano."""
    tier = plan_tier.upper()
    unit_price = PLAN_PRICES.get(tier)
    if unit_price is None:
        raise ValueError(f"plan_tier inválido: {tier}")

    if not settings.MP_ACCESS_TOKEN:
        raise ValueError("MP_ACCESS_TOKEN não configurado")

    preference_data: dict[str, Any] = {
        "items": [
            {
                "title": f"Plano {tier}",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(unit_price),
            }
        ],
        "external_reference": f"{user.id}:{tier}",
        "notification_url": settings.WEBHOOK_URL,
    }

    def _create() -> dict[str, Any]:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        return sdk.preference().create(preference_data)

    result = await anyio.to_thread.run_sync(_create)
    response = result.get("response") or {}
    init_point = response.get("init_point") or response.get("sandbox_init_point")
    if not init_point:
        raise RuntimeError("Mercado Pago não retornou init_point")
    return str(init_point)


# ── Preferência de upgrade (paga apenas a diferença) ──────────────────────

async def create_upgrade_preference(
    user: User,
    target_tier: str,
    diff_price: float,
) -> str:
    """Cria a preferência de pagamento para upgrade, cobrando só a diferença."""
    tier = target_tier.upper()

    if not settings.MP_ACCESS_TOKEN:
        raise ValueError("MP_ACCESS_TOKEN não configurado")

    preference_data: dict[str, Any] = {
        "items": [
            {
                "title": f"Upgrade para {tier}",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": round(float(diff_price), 2),
            }
        ],
        # Formato especial para o webhook detectar upgrade
        "external_reference": f"{user.id}:UPGRADE:{tier}",
        "notification_url": settings.WEBHOOK_URL,
    }

    def _create() -> dict[str, Any]:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        return sdk.preference().create(preference_data)

    result = await anyio.to_thread.run_sync(_create)
    response = result.get("response") or {}
    init_point = response.get("init_point") or response.get("sandbox_init_point")
    if not init_point:
        raise RuntimeError("Mercado Pago não retornou init_point")
    return str(init_point)


# ── Webhook: Validação Segura e Ativação ──────────────────────────────────

async def verify_payment_and_activate(payment_id: str, db: AsyncSession) -> None:
    """Consulte ativamente a API do MP para verificar o pagamento real e lidar com ativações."""
    if not settings.MP_ACCESS_TOKEN:
        raise ValueError("MP_ACCESS_TOKEN não configurado")

    def _get_payment() -> dict[str, Any]:
        return sdk_instance.payment().get(str(payment_id))

    mp_result = await asyncio.to_thread(_get_payment)
    
    if mp_result.get("status") not in (200, 201):
        raise ValueError(f"Pagamento com ID {payment_id} não encontrado ou inválido no Mercado Pago.")
        
    payment_info = mp_result.get("response") or {}
    
    mp_status = str(payment_info.get("status") or "pending")
    amount = float(payment_info.get("transaction_amount") or 0.0)
    external_ref = str(payment_info.get("external_reference") or "")
    
    # Valida formato UUID
    try:
        user_id = UUID(external_ref)
    except ValueError:
        return # Formato de user_id não reconhecido ou legacy, sai em silêncio
    
    # ── Registo na Tabela Payment ──────────────────────────────────────────
    try:
        existing_payment = await db.scalar(
            select(Payment).where(Payment.external_reference == str(payment_id))
        )
        if existing_payment is None:
            db.add(
                Payment(
                    user_id=user_id,
                    external_reference=str(payment_id),
                    amount=amount,
                    status=mp_status,
                )
            )
        else:
            existing_payment.status = mp_status
            existing_payment.amount = amount
            
        await db.flush()

        # ── Regra de Negócio Crucial: Ativar PENDING => ACTIVE ─────────────
        if mp_status == "approved":
            import logging
            logger = logging.getLogger(__name__)
            
            enrollment = await db.scalar(
                select(Enrollment)
                .where(
                    Enrollment.user_id == user_id,
                    Enrollment.status == "PENDING"
                )
                .order_by(Enrollment.created_at.desc())
            )
            
            if enrollment:
                enrollment.status = "ACTIVE"
                # Calcula expiração baseada no formato do plan_tier do banco
                tier = enrollment.plan_tier.upper()
                duration_days = PLAN_DURATION_DAYS.get(tier, 30) # Default a 30 se não encontrar
                now = datetime.now(timezone.utc)
                enrollment.expires_at = now + timedelta(days=duration_days)
                
                logger.info(f"Acesso liberado para usuário: {user_id} - Plano: {tier}")
                
        elif mp_status in ["rejected", "cancelled"]:
            import logging
            logger = logging.getLogger(__name__)
            
            enrollment = await db.scalar(
                select(Enrollment)
                .where(
                    Enrollment.user_id == user_id,
                    Enrollment.status == "PENDING"
                )
                .order_by(Enrollment.created_at.desc())
            )
            
            if enrollment:
                enrollment.status = "CANCELLED"
                logger.info(f"Matrícula cancelada para o usuário: {user_id} devido a pagamento {mp_status}")
                
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


# ── Webhook de pagamento ───────────────────────────────────────────────────

async def process_webhook(payment_data: dict[str, Any], db: AsyncSession) -> None:
    if not settings.MP_ACCESS_TOKEN:
        raise ValueError("MP_ACCESS_TOKEN não configurado")

    payment_id = (
        (payment_data.get("data") or {}).get("id")
        or payment_data.get("id")
        or (payment_data.get("payment") or {}).get("id")
    )
    if not payment_id:
        return

    def _get_payment() -> dict[str, Any]:
        sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)
        return sdk.payment().get(str(payment_id))

    mp_result = await anyio.to_thread.run_sync(_get_payment)
    payment = mp_result.get("response") or {}

    mp_status = str(payment.get("status") or "pending")
    amount = float(payment.get("transaction_amount") or 0.0)
    external_ref = str(payment.get("external_reference") or "")

    # ── Parse do external_reference ──────────────────────────────────────
    # Formatos possíveis:
    #   uuid:TIER           → compra inicial (ex: uuid:BASIC)
    #   uuid:UPGRADE:TIER   → upgrade (ex: uuid:UPGRADE:PREMIUM)
    user_id: UUID | None = None
    plan_tier: str | None = None
    is_upgrade = False

    parts = external_ref.split(":")
    try:
        user_id = UUID(parts[0])
        if len(parts) == 3 and parts[1].upper() == "UPGRADE":
            plan_tier = parts[2].upper()
            is_upgrade = True
        elif len(parts) == 2:
            plan_tier = parts[1].upper()
        else:
            return
    except (ValueError, IndexError):
        return

    if user_id is None or plan_tier is None:
        return

    try:
        # Registra / atualiza o Payment
        existing_payment = await db.scalar(
            select(Payment).where(Payment.external_reference == str(payment_id))
        )
        if existing_payment is None:
            db.add(
                Payment(
                    user_id=user_id,
                    external_reference=str(payment_id),
                    amount=amount,
                    status=mp_status,
                )
            )
        else:
            existing_payment.status = mp_status
            existing_payment.amount = amount

        if mp_status == "approved":
            now = datetime.now(timezone.utc)
            duration_days = PLAN_DURATION_DAYS.get(plan_tier, 365)
            expires_at = now + timedelta(days=duration_days)

            if is_upgrade:
                # Atualiza o enrollment ativo para o novo tier
                enrollment = await db.scalar(
                    select(Enrollment)
                    .where(
                        Enrollment.user_id == user_id,
                        Enrollment.status == "ACTIVE",
                    )
                    .order_by(Enrollment.created_at.desc())
                )
                if enrollment is None:
                    # Fallback: cria um enrollment novo
                    db.add(
                        Enrollment(
                            user_id=user_id,
                            plan_tier=plan_tier,
                            status="ACTIVE",
                            expires_at=expires_at,
                        )
                    )
                else:
                    enrollment.plan_tier = plan_tier
                    enrollment.status = "ACTIVE"
                    enrollment.expires_at = expires_at
            else:
                # Compra inicial: busca ou cria enrollment para o tier
                enrollment = await db.scalar(
                    select(Enrollment)
                    .where(Enrollment.user_id == user_id, Enrollment.plan_tier == plan_tier)
                    .order_by(Enrollment.created_at.desc())
                )
                if enrollment is None:
                    db.add(
                        Enrollment(
                            user_id=user_id,
                            plan_tier=plan_tier,
                            status="ACTIVE",
                            expires_at=expires_at,
                        )
                    )
                else:
                    enrollment.status = "ACTIVE"
                    enrollment.expires_at = expires_at

        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
