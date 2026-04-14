"""Rotas do aluno autenticado."""

import logging
import traceback
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.course import Course, Lesson, Module
from app.models.enrollment import Enrollment
from app.models.package import Package
from app.models.progress import LessonProgress
from app.models.user import User
from app.schemas.course import CourseOut, CourseStudentDetailOut, CourseStudentOut
from app.schemas.dashboard import StudentDashboardOut
from app.schemas.progress import ProgressOut

router = APIRouter()

# ── Hierarquia e preços dos planos ────────────────────────────────────────
PLAN_HIERARCHY: list[str] = ["MENSAL", "BASICO", "PREMIUM"]
PLAN_PRICES: dict[str, float] = {
    "MENSAL": 9.90,
    "BASICO": 598.80,
    "PREMIUM": 1078.80,
}


def normalize_tier(tier: str | None) -> str:
    """Normaliza nomes de tiers (ex: BASIC -> BASICO)."""
    if not tier:
        return "FREE"
    t = tier.upper().strip()
    if t in ["BASIC", "BASE", "BÁSICO"]:
        return "BASICO"
    if t in ["AVULSO", "MONTHLY", "MENSAL"]:
        return "MENSAL"
    return t


def _tier_index(tier: str) -> int:
    """Retorna o índice do plano na hierarquia (maior = mais completo)."""
    try:
        norm_tier = normalize_tier(tier)
        return PLAN_HIERARCHY.index(norm_tier)
    except ValueError:
        return -1


# ── GET /student/courses ───────────────────────────────────────────────────

@router.get("/courses", response_model=list[CourseStudentOut])
async def student_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CourseStudentOut]:
    """Retorna TODOS os cursos publicados com lógica de Vitrine e Upsell (Abordagem Segura)."""
    from app.models.course import Course
    from app.models.enrollment import Enrollment
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    try:
        now = datetime.now(timezone.utc)

        # 1. Qual é o plano atual do aluno?
        stmt = (
            select(Enrollment)
            .where(
                Enrollment.user_id == current_user.id,
                Enrollment.status == "ACTIVE",
                (Enrollment.expires_at.is_(None) | (Enrollment.expires_at > now)),
            )
            .order_by(Enrollment.created_at.desc())
            .limit(1)
        )
        enrollment = await db.scalar(stmt)
        student_plan = normalize_tier(enrollment.plan_tier) if enrollment else "FREE"
        student_idx = _tier_index(student_plan)
        student_price = PLAN_PRICES.get(student_plan, 0.0)

        # 2. Busca a vitrine (Todos os cursos publicados)
        stmt_courses = (
            select(Course)
            .where(Course.is_published == True)
            .options(selectinload(Course.packages))
            .order_by(Course.created_at.desc())
        )
        result = await db.execute(stmt_courses)
        all_courses = result.scalars().all()

        # 3. Lógica do Cadeado (Upsell com dicionário seguro)
        output: list[dict] = []
        for course in all_courses:
            # Converte o objeto do banco para dicionário para permitir injeção dinâmica
            course_dict = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "price": course.price,
                "thumbnail_url": course.thumbnail_url,
                "instructor": course.instructor,
                "level": course.level,
                "duration": course.duration,
                "is_published": course.is_published,
                "created_at": course.created_at,
                "package_ids": [p.id for p in course.packages] if course.packages else []
            }

            # Extrai os tiers dos pacotes vinculados (Normalizados)
            course_tiers = [normalize_tier(p.tier_name) for p in course.packages] if course.packages else []
            
            # Motor do Cadeado
            is_locked = True
            if not course_tiers or student_plan == 'PREMIUM' or student_plan in course_tiers:
                is_locked = False
            
            price_diff = 0.0
            required_tier = None
            if is_locked:
                accessible_tiers = [t for t in course_tiers if _tier_index(t) > student_idx]
                if accessible_tiers:
                    accessible_tiers.sort(key=_tier_index)
                    required_tier = accessible_tiers[0]
                    price_diff = round(PLAN_PRICES.get(required_tier, 0.0) - student_price, 2)
                else:
                    price_diff = 99.90
            
            course_dict['is_locked'] = is_locked
            course_dict['upgrade_price_difference'] = max(0.0, price_diff) if is_locked else 0.0
            course_dict['required_tier'] = required_tier
            
            output.append(course_dict)
                
        return output

    except Exception as e:
        import traceback
        logging.error(f"Erro crítico no motor de cursos: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Erro ao carregar os cursos"
        )

@router.get("/courses/{course_id}", response_model=CourseStudentDetailOut)
async def student_course_detail(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CourseStudentDetailOut:
    """Retorna os detalhes de um curso específico para o aluno, incluindo módulos, aulas e progresso."""
    try:
        now = datetime.now(timezone.utc)

        # 1. Qual é o plano atual do aluno?
        stmt_enroll = (
            select(Enrollment)
            .where(
                Enrollment.user_id == current_user.id,
                Enrollment.status == "ACTIVE",
                (Enrollment.expires_at.is_(None) | (Enrollment.expires_at > now)),
            )
            .order_by(Enrollment.created_at.desc())
            .limit(1)
        )
        enrollment = await db.scalar(stmt_enroll)
        student_plan = normalize_tier(enrollment.plan_tier) if enrollment else "FREE"
        student_idx = _tier_index(student_plan)
        student_price = PLAN_PRICES.get(student_plan, 0.0)

        # 2. Busca o curso com módulos e aulas
        stmt_course = (
            select(Course)
            .where(Course.id == course_id, Course.is_published == True)
            .options(
                selectinload(Course.packages),
                selectinload(Course.modules).selectinload(Module.lessons)
            )
        )
        course = await db.scalar(stmt_course)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado")

        # 3. Lógica do Cadeado
        course_tiers = [normalize_tier(p.tier_name) for p in course.packages] if course.packages else []
        is_locked = True
        if not course_tiers or student_plan == 'PREMIUM' or student_plan in course_tiers:
            is_locked = False

        required_tier = None
        price_diff = 0.0
        if is_locked:
            accessible_tiers = [t for t in course_tiers if _tier_index(t) > student_idx]
            if accessible_tiers:
                accessible_tiers.sort(key=_tier_index)
                required_tier = accessible_tiers[0]
                price_diff = round(PLAN_PRICES.get(required_tier, 0.0) - student_price, 2)
            else:
                price_diff = 99.90

        # 4. Se estiver bloqueado, retorna apenas meta-dados
        if is_locked:
            return CourseStudentDetailOut(
                id=course.id,
                title=course.title,
                description=course.description,
                price=course.price,
                thumbnail_url=course.thumbnail_url,
                is_published=course.is_published,
                created_at=course.created_at,
                package_ids=[p.id for p in course.packages],
                is_locked=True,
                upgrade_price_difference=max(0.0, price_diff),
                required_tier=required_tier,
                modules=[],
                overall_progress=0.0
            )

        # 5. Se desbloqueado, processa progresso
        stmt_prog = select(LessonProgress.lesson_id).where(LessonProgress.user_id == current_user.id)
        prog_result = await db.execute(stmt_prog)
        completed_lesson_ids = set(prog_result.scalars().all())

        total_lessons = 0
        completed_count = 0
        modules_out = []

        for mod in course.modules:
            lessons_out = []
            for lesson in mod.lessons:
                total_lessons += 1
                is_completed = lesson.id in completed_lesson_ids
                if is_completed:
                    completed_count += 1
                
                lessons_out.append({
                    "id": lesson.id,
                    "module_id": lesson.module_id,
                    "title": lesson.title,
                    "content": lesson.content,
                    "video_url": lesson.video_url,
                    "order": lesson.order,
                    "is_free_preview": lesson.is_free_preview,
                    "created_at": lesson.created_at,
                    "completed": is_completed
                })
            
            modules_out.append({
                "id": mod.id,
                "course_id": mod.course_id,
                "title": mod.title,
                "order": mod.order,
                "lessons": lessons_out
            })

        overall_progress = (completed_count / total_lessons * 100) if total_lessons > 0 else 0.0

        return CourseStudentDetailOut(
            id=course.id,
            title=course.title,
            description=course.description,
            price=course.price,
            thumbnail_url=course.thumbnail_url,
            instructor=course.instructor,
            level=course.level,
            duration=course.duration,
            is_published=course.is_published,
            created_at=course.created_at,
            package_ids=[p.id for p in course.packages],
            is_locked=False,
            upgrade_price_difference=0.0,
            required_tier=None,
            modules=modules_out,
            overall_progress=round(overall_progress, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logging.error(f"Erro ao carregar detalhes do curso: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar detalhes do curso"
        )


# ── GET /student/dashboard ─────────────────────────────────────────────────

@router.get("/dashboard", response_model=StudentDashboardOut)
async def student_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudentDashboardOut:
    """Consolida status, progresso e a vitrine de cursos para o aluno."""
    try:
        now = datetime.now(timezone.utc)
        
        # 1. Busca Matrícula Atuai
        stmt_enroll = (
            select(Enrollment)
            .where(
                Enrollment.user_id == current_user.id,
                Enrollment.status == "ACTIVE",
                (Enrollment.expires_at.is_(None) | (Enrollment.expires_at > now)),
            )
            .order_by(Enrollment.created_at.desc())
        )
        enrollment = await db.scalar(stmt_enroll)
        
        # 2. Busca Aulas Concluídas
        result_prog = await db.execute(
            select(LessonProgress.lesson_id).where(LessonProgress.user_id == current_user.id)
        )
        completed_lessons = list(result_prog.scalars().all())

        # 3. Lógica da Vitrine (Reaproveitada de student_courses)
        student_plan = normalize_tier(enrollment.plan_tier) if enrollment else "FREE"
        student_idx = _tier_index(student_plan)
        student_price = PLAN_PRICES.get(student_plan, 0.0)

        stmt_courses = (
            select(Course)
            .where(Course.is_published == True)
            .options(selectinload(Course.packages))
            .order_by(Course.created_at.desc())
        )
        result_courses = await db.execute(stmt_courses)
        all_courses = result_courses.scalars().all()

        courses_output = []
        for course in all_courses:
            course_tiers = [normalize_tier(p.tier_name) for p in course.packages] if course.packages else []
            
            is_locked = True
            if not course_tiers or student_plan == 'PREMIUM' or student_plan in course_tiers:
                is_locked = False
            
            price_diff = 0.0
            required_tier = None
            if is_locked:
                accessible_tiers = [t for t in course_tiers if _tier_index(t) > student_idx]
                if accessible_tiers:
                    accessible_tiers.sort(key=_tier_index)
                    required_tier = accessible_tiers[0]
                    price_diff = round(PLAN_PRICES.get(required_tier, 0.0) - student_price, 2)
            
            courses_output.append({
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "price": course.price,
                "thumbnail_url": course.thumbnail_url,
                "instructor": course.instructor,
                "level": course.level,
                "duration": course.duration,
                "is_published": course.is_published,
                "created_at": course.created_at,
                "package_ids": [p.id for p in course.packages] if course.packages else [],
                "is_locked": is_locked,
                "upgrade_price_difference": max(0.0, price_diff) if is_locked else 0.0,
                "required_tier": required_tier
            })

        return StudentDashboardOut(
            active_plan=student_plan,
            completed_lessons=completed_lessons,
            status="ACTIVE" if enrollment else "PENDING", # "PENDING" ou outro se não houver matrícula ativa
            courses=courses_output
        )

    except Exception as e:
        import traceback
        logging.error(f"Erro no dashboard do aluno: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar o dashboard"
        )


# ── POST /student/lessons/{id}/complete ───────────────────────────────────

@router.post("/lessons/{lesson_id}/complete", response_model=ProgressOut)
async def complete_lesson(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProgressOut:
    existing = await db.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id
        )
    )
    if existing is not None:
        return existing

    progress = LessonProgress(
        user_id=current_user.id,
        lesson_id=lesson_id,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(progress)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar progresso",
        ) from exc

    saved = await db.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id, LessonProgress.lesson_id == lesson_id
        )
    )
    if saved is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro inesperado")
    return saved
