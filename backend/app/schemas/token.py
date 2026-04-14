"""Schemas de autenticação e payload de token."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str | None = None
    session_id: str | None = None
