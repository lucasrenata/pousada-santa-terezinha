"""Ponto de entrada da aplicação FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://localhost:5181",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180",
        "http://127.0.0.1:5181",
        "https://formacao.visionaria.ia.br",
        "https://api.visionaria.ia.br",
        "https://portal.visionaria.ia.br",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Device-Fingerprint", "X-Browser-Info", "Authorization"],
    expose_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "db": "configured"}


app.include_router(api_router, prefix="/api/v1")

# Servir arquivos estáticos (uploads)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

