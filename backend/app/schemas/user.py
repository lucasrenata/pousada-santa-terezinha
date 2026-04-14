"""Schemas do usuário (entrada e saída)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    password: str
    plan_tier: str | None = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("A nova senha deve ter no mínimo 8 caracteres.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: str
    browser_info: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
    # AI Preferences
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None


from app.schemas.enrollment import EnrollmentOut

class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    is_active: bool
    created_at: datetime
    
    @field_validator("role", mode="before")
    @classmethod
    def enum_to_str(cls, v) -> str:
        if hasattr(v, "value"):
            return v.value
        return str(v)
    plan_tier: str | None = None
    enrollments: list[EnrollmentOut] | None = None
    
    # AI Preferences (Safe)
    ai_provider: str | None = None
    ai_model: str | None = None
    has_ai_api_key: bool = False
