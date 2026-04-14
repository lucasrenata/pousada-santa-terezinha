"""Rotas administrativas protegidas."""

import traceback
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.enrollment import Enrollment
from app.models.lead import Lead
from app.models.package import Package
from app.models.payment import Payment
from app.models.user import User, UserRole
from app.schemas.dashboard import AdminMetricsOut
from app.schemas.lead import LeadOut
from app.schemas.package import PackageCreate, PackageOut, PackageUpdate
from app.schemas.user import UserOut, UserCreate

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


# ── USERS ──────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    try:
        result = await db.execute(
            select(User)
            .options(selectinload(User.enrollments))
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar usuários",
        ) from exc

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Cria um novo usuário (aluno) via painel administrativo."""
    try:
        # 1. Verifica se o e-mail já existe
        stmt = select(User).where(User.email == user_in.email)
        existing_user = await db.scalar(stmt)
        if existing_user is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

        # 2. Extrai o plan_tier se informado
        plan_tier = user_in.plan_tier
        user_data = user_in.model_dump(exclude={"plan_tier", "password"})

        # 3. Cria o usuário
        user = User(
            **user_data,
            hashed_password=get_password_hash(user_in.password),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(user)
        
        # É VITAL comitar aqui para gerar o user.id antes de criar a matrícula
        await db.commit()
        await db.refresh(user)

        # 4. Cria a matrícula se plan_tier foi informado
        if plan_tier:
            plan_tier = plan_tier.upper()
            days_to_expire = 30 if plan_tier == 'MENSAL' else 365
            expires_at = datetime.now(timezone.utc) + timedelta(days=days_to_expire)

            enrollment = Enrollment(
                user_id=user.id,
                plan_tier=plan_tier,
                status='ACTIVE',
                payment_method='MANUAL_ADMIN',
                expires_at=expires_at
            )
            db.add(enrollment)
            await db.commit()
            await db.refresh(user) # Refresh para carregar a relação se necessário

        return user

    except HTTPException:
        await db.rollback()
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        logging.error(f"Erro de Banco de Dados na criação Admin: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao salvar no banco: verifique se os dados estão corretos.",
        ) from exc
    except Exception as exc:
        await db.rollback()
        error_trace = traceback.format_exc()
        logging.error(f"Erro Crítico 500 na criação Admin: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Remove um usuário do sistema."""
    try:
        stmt = delete(User).where(User.id == user_id)
        await db.execute(stmt)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir usuário",
        ) from exc


# ── DASHBOARD ──────────────────────────────────────────────────────────────

@router.get("/dashboard/metrics", response_model=AdminMetricsOut)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> AdminMetricsOut:
    """Retorna métricas para o dashboard admin com fallback defensivo."""
    
    # 1. Alunos
    try:
        total_students = await db.scalar(
            select(func.count(User.id)).where(User.role != UserRole.ADMIN)
        )
    except Exception as e:
        logging.error(f"Erro ao contar usuários: {e}")
        total_students = 0

    # 2. Matrículas
    try:
        active_enrollments = await db.scalar(
            select(func.count(Enrollment.id)).where(Enrollment.status == "ACTIVE")
        )
    except Exception as e:
        logging.error(f"Erro ao contar matrículas: {e}")
        active_enrollments = 0

    # 3. Leads (Seguro: sem filtro de status se houver dúvida sobre a coluna)
    try:
        pending_leads = await db.scalar(select(func.count(Lead.id)))
    except Exception as e:
        logging.error(f"Erro ao contar leads: {e}")
        pending_leads = 0

    # 4. Receita
    try:
        total_revenue = await db.scalar(
            select(func.sum(Payment.amount)).where(
                Payment.status.in_(["PAID", "approved", "completed"])
            )
        ) or 0.0
    except Exception as e:
        logging.error(f"Erro ao calcular receita: {e}")
        total_revenue = 0.0

    return AdminMetricsOut(
        total_users=total_students or 0,
        active_enrollments=active_enrollments or 0,
        pending_leads=pending_leads or 0,
        total_revenue=float(total_revenue),
    )


# ── PACKAGES ────────────────────────────────────────────────────────────────

@router.post("/packages", response_model=PackageOut, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_in: PackageCreate,
    db: AsyncSession = Depends(get_db)
) -> PackageOut:
    package = Package(**package_in.model_dump())
    db.add(package)
    try:
        await db.commit()
        await db.refresh(package)
        return package
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar pacote",
        ) from exc


@router.get("/packages", response_model=list[PackageOut])
async def list_packages(
    db: AsyncSession = Depends(get_db)
) -> list[PackageOut]:
    try:
        result = await db.execute(select(Package).order_by(Package.created_at.desc()))
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar pacotes",
        ) from exc


@router.get("/packages/{package_id}", response_model=PackageOut)
async def get_package(package_id: UUID, db: AsyncSession = Depends(get_db)) -> PackageOut:
    stmt = select(Package).where(Package.id == package_id)
    package = await db.scalar(stmt)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pacote não encontrado")
    return package


@router.put("/packages/{package_id}", response_model=PackageOut)
async def update_package(
    package_id: UUID,
    package_in: PackageUpdate,
    db: AsyncSession = Depends(get_db)
) -> PackageOut:
    stmt = select(Package).where(Package.id == package_id)
    package = await db.scalar(stmt)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pacote não encontrado")
    
    update_data = package_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(package, key, value)
    
    try:
        await db.commit()
        await db.refresh(package)
        return package
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar pacote",
        ) from exc


@router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(package_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    stmt = select(Package).where(Package.id == package_id)
    package = await db.scalar(stmt)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pacote não encontrado")
    
    try:
        await db.delete(package)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir pacote",
        ) from exc


# ── LEADS ──────────────────────────────────────────────────────────────────

@router.get("/leads", response_model=list[LeadOut])
async def list_leads(db: AsyncSession = Depends(get_db)) -> list[LeadOut]:
    logging.info("Admin listando leads")
    try:
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar leads",
        ) from exc


@router.delete("/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Remove um lead do sistema."""
    try:
        stmt = delete(Lead).where(Lead.id == lead_id)
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado")
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir lead",
        ) from exc
