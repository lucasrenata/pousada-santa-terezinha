"""CRUD administrativo de cursos, módulos e aulas."""

import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin_user
from app.core.database import get_db
from app.models.course import Course, Lesson, Module
from app.models.package import Package
from app.schemas.course import (
    CourseCreate,
    CourseOut,
    CourseUpdate,
    CourseDetailOut,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    ModuleCreate,
    ModuleOut,
    ModuleUpdate,
)

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


# ── CURSOS ─────────────────────────────────────────────────────────────────

@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_in: CourseCreate,
    db: AsyncSession = Depends(get_db),
) -> CourseOut:
    try:
        # Extrai package_ids antes de criar o curso
        package_ids = course_in.package_ids
        course_data = course_in.model_dump(exclude={"package_ids"})

        course = Course(**course_data)

        # Vincula pacotes se informados
        if package_ids:
            result = await db.execute(select(Package).where(Package.id.in_(package_ids)))
            packages = list(result.scalars().all())
            course.packages = packages

        db.add(course)
        await db.commit()
        await db.refresh(course)
        
        # Recarrega com pacotes para evitar erro de greenlet no property package_ids
        stmt = select(Course).where(Course.id == course.id).options(selectinload(Course.packages))
        course = await db.scalar(stmt)
        return course
    except Exception as exc:
        await db.rollback()
        import logging
        logging.exception("Erro ao criar curso")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar curso: {str(exc)}",
        ) from exc


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(db: AsyncSession = Depends(get_db)) -> list[CourseOut]:
    try:
        stmt = select(Course).options(selectinload(Course.packages)).order_by(Course.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar cursos",
        ) from exc


@router.get("/courses/{course_id}", response_model=CourseDetailOut)
async def get_course_detail_admin(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CourseDetailOut:
    """Retorna detalhes completos do curso (módulos e aulas) para o editor admin."""
    try:
        stmt = (
            select(Course)
            .where(Course.id == course_id)
            .options(
                selectinload(Course.modules).selectinload(Module.lessons),
                selectinload(Course.packages)
            )
        )
        course = await db.scalar(stmt)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar curso no painel admin",
        ) from exc

    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")
    return course


@router.put("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: UUID,
    course_in: CourseUpdate,
    db: AsyncSession = Depends(get_db),
) -> CourseOut:
    package_ids = course_in.package_ids
    values = course_in.model_dump(exclude_unset=True, exclude={"package_ids"})

    if not values and package_ids is None:
        course = await db.scalar(select(Course).where(Course.id == course_id))
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")
        return course

    try:
        if values:
            await db.execute(update(Course).where(Course.id == course_id).values(**values))

        # Atualiza vínculos de pacotes se packet_ids fornecido
        if package_ids is not None:
            stmt = (
                select(Course)
                .where(Course.id == course_id)
                .options(selectinload(Course.packages))
            )
            course = await db.scalar(stmt)
            if course is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")

            pkg_result = await db.execute(select(Package).where(Package.id.in_(package_ids)))
            course.packages = list(pkg_result.scalars().all())

        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar curso",
        ) from exc

    course = await db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(selectinload(Course.packages))
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")
    return course


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    try:
        result = await db.execute(delete(Course).where(Course.id == course_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir curso",
        ) from exc


# ── MÓDULOS ────────────────────────────────────────────────────────────────

@router.post("/courses/{course_id}/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
async def create_module(
    course_id: UUID,
    module_in: ModuleCreate,
    db: AsyncSession = Depends(get_db),
) -> ModuleOut:
    try:
        # 1. Verifica se o curso existe
        course = await db.scalar(select(Course).where(Course.id == course_id))
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")

        # 2. Cria o módulo
        module = Module(course_id=course_id, **module_in.model_dump())
        db.add(module)
        await db.commit()
        await db.refresh(module)

        # Carrega relacionamentos para evitar erro de greenlet na serialização (lessons)
        stmt = select(Module).where(Module.id == module.id).options(selectinload(Module.lessons))
        module = await db.scalar(stmt)
        return module

    except HTTPException:
        await db.rollback()
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        import logging
        logging.error(f"Erro de Banco de Dados: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao salvar no banco: verifique se os dados estão corretos.",
        ) from exc
    except Exception as exc:
        await db.rollback()
        error_trace = traceback.format_exc()
        import logging
        logging.error(f"Erro Crítico 500: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(exc)}",
        ) from exc


@router.put("/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: UUID,
    module_in: ModuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> ModuleOut:
    values = module_in.model_dump(exclude_unset=True)
    if not values:
        module = await db.scalar(select(Module).where(Module.id == module_id))
        if module is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado")
        return module

    try:
        await db.execute(update(Module).where(Module.id == module_id).values(**values))
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar módulo",
        ) from exc

    module = await db.scalar(
        select(Module)
        .where(Module.id == module_id)
        .options(selectinload(Module.lessons))
    )
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado")
    return module


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(module_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    try:
        result = await db.execute(delete(Module).where(Module.id == module_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado")
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir módulo",
        ) from exc


# ── AULAS ──────────────────────────────────────────────────────────────────

@router.post("/modules/{module_id}/lessons", response_model=LessonOut, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    module_id: UUID,
    lesson_in: LessonCreate,
    db: AsyncSession = Depends(get_db),
) -> LessonOut:
    module = await db.scalar(select(Module).where(Module.id == module_id))
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado")

    lesson = Lesson(module_id=module_id, **lesson_in.model_dump())
    db.add(lesson)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar aula",
        ) from exc
    await db.refresh(lesson)
    return lesson


@router.put("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    lesson_id: UUID,
    lesson_in: LessonUpdate,
    db: AsyncSession = Depends(get_db),
) -> LessonOut:
    values = lesson_in.model_dump(exclude_unset=True)
    if not values:
        lesson = await db.scalar(select(Lesson).where(Lesson.id == lesson_id))
        if lesson is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula não encontrada")
        return lesson

    try:
        await db.execute(update(Lesson).where(Lesson.id == lesson_id).values(**values))
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar aula",
        ) from exc

    lesson = await db.scalar(select(Lesson).where(Lesson.id == lesson_id))
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula não encontrada")
    return lesson


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    try:
        result = await db.execute(delete(Lesson).where(Lesson.id == lesson_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula não encontrada")
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir aula",
        ) from exc
