"""Schemas de cursos, módulos e aulas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LessonBase(BaseModel):
    title: str
    content: str
    video_url: str | None = None
    order: int = 1
    is_free_preview: bool = False


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    video_url: str | None = None
    order: int | None = None
    is_free_preview: bool | None = None


class LessonOut(LessonBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    module_id: UUID
    created_at: datetime


class LessonStudentOut(LessonOut):
    """Schema para aula na área do aluno com status de conclusão."""
    completed: bool = False


class ModuleBase(BaseModel):
    title: str
    order: int = 1


class ModuleCreate(ModuleBase):
    pass


class ModuleUpdate(BaseModel):
    title: str | None = None
    order: int | None = None


class ModuleOut(ModuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    created_at: datetime
    lessons: list[LessonOut] = []


class ModuleStudentOut(ModuleBase):
    """Schema para módulo na área do aluno."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    lessons: list[LessonStudentOut] = []


class CourseBase(BaseModel):
    title: str
    description: str | None = None
    price: float
    thumbnail_url: str | None = None
    instructor: str | None = None
    level: str | None = None
    duration: str | None = None
    is_published: bool = False


class CourseCreate(CourseBase):
    package_ids: list[UUID] = []


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: float | None = None
    thumbnail_url: str | None = None
    instructor: str | None = None
    level: str | None = None
    duration: str | None = None
    is_published: bool | None = None
    package_ids: list[UUID] | None = None


class CourseOut(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    package_ids: list[UUID] = []
    is_locked: bool = False
    upgrade_price_difference: float = 0.0


from app.schemas.package import PackageOut


class CourseDetailOut(CourseOut):
    modules: list[ModuleOut] = []
    packages: list[PackageOut] = []


class CourseStudentOut(CourseOut):
    """Schema de saída para a área de aluno com controle de acesso por pacote."""

    required_tier: str | None = None


class CourseStudentDetailOut(CourseStudentOut):
    """Schema detalhado para a página do curso na área do aluno."""
    modules: list[ModuleStudentOut] = []
    overall_progress: float = 0.0
