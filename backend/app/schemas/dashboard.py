from uuid import UUID

from pydantic import BaseModel


class AdminMetricsOut(BaseModel):
    total_users: int
    active_enrollments: int
    total_revenue: float
    pending_leads: int


from app.schemas.course import CourseStudentOut


class StudentDashboardOut(BaseModel):
    active_plan: str | None
    completed_lessons: list[UUID]
    status: str
    courses: list[CourseStudentOut] = []
