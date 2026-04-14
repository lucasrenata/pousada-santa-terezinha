"""Rotas públicas e autenticadas do catálogo."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.course import Course, Module
from app.models.package import Package
from app.models.user import User
from app.schemas.course import CourseDetailOut, CourseOut
from app.schemas.package import PackageOut

router = APIRouter()


# ── PACOTES (público) ──────────────────────────────────────────────────────

@router.get("/packages", response_model=list[PackageOut])
async def list_active_packages(db: AsyncSession = Depends(get_db)) -> list[PackageOut]:
    """Retorna os pacotes ativos ordenados por preço (consumido pela Landing Page)."""
    try:
        result = await db.execute(
            select(Package)
            .where(Package.is_active.is_(True))
            .order_by(Package.price.asc())
        )
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar pacotes",
        ) from exc


# ── CURSOS (público) ───────────────────────────────────────────────────────

@router.get("/courses", response_model=list[CourseOut])
async def list_published_courses(db: AsyncSession = Depends(get_db)) -> list[CourseOut]:
    try:
        result = await db.execute(
            select(Course).where(Course.is_published.is_(True)).order_by(Course.created_at.desc())
        )
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar cursos",
        ) from exc


@router.get("/courses/{course_id}", response_model=CourseDetailOut)
async def get_course_detail(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CourseDetailOut:
    _ = current_user
    try:
        stmt = (
            select(Course)
            .where(Course.id == course_id, Course.is_published.is_(True))
            .options(selectinload(Course.modules).selectinload(Module.lessons))
        )
        course = await db.scalar(stmt)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar curso",
        ) from exc

    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")
    return course
