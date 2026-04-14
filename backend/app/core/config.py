"""Configurações centrais do projeto (via variáveis de ambiente)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = Field(default="Plataforma de Cursos SaaS")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/plataforma_curso"
    )
    SECRET_KEY: str = Field(default="CHANGE_ME")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    MP_ACCESS_TOKEN: str = Field(default="APP_USR-seu-token-aqui")
    FRONTEND_URL: str = Field(default="https://formacao.visionaria.ia.br")
    WEBHOOK_SECRET: str = Field(default="")
    NGROK_URL: str = Field(default="")
    WEBHOOK_URL: str = Field(default="https://api.visionaria.ia.br/api/v1/webhooks/mercadopago")

    # Email Settings
    MAIL_USERNAME: str = Field(default="seu_email@gmail.com")
    MAIL_PASSWORD: str = Field(default="app_password")
    MAIL_FROM: str = Field(default="seu_email@gmail.com")
    MAIL_FROM_NAME: str = Field(default="ParcerIA")
    MAIL_SERVER: str = Field(default="smtp.gmail.com")
    MAIL_PORT: int = Field(default=587)
    MAIL_STARTTLS: bool = Field(default=True)
    MAIL_SSL_TLS: bool = Field(default=False)
    USE_CREDENTIALS: bool = Field(default=True)
    VALIDATE_CERTS: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()
