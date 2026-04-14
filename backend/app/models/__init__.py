"""Modelos SQLAlchemy.

Este módulo centraliza importações para facilitar o carregamento pelo Alembic.
"""

from app.models.base import Base
from app.models.course import Course, Lesson, Module
from app.models.enrollment import Enrollment
from app.models.lead import Lead
from app.models.package import Package, package_courses
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.progress import LessonProgress
from app.models.portal import PortalSlide, PortalVideo
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Lead",
    "Plan",
    "Package",
    "package_courses",
    "Course",
    "Module",
    "Lesson",
    "Enrollment",
    "Payment",
    "LessonProgress",
    "PortalSlide",
    "PortalVideo",
]

