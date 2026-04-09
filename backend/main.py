from pathlib import Path
from dotenv import load_dotenv
import os

# Carrega variáveis de ambiente antes de qualquer outro import que dependa delas
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine
import models
from routers import auth, guests, rooms, bookings, products, finance, settings, payments, admin, chat, events, webhook_whatsapp
import sys

# Tabelas no banco agora são gerenciadas via migrations do Alembic.
# Removido: models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pousada System Modular", version="1.0.0")

# --- CONFIGURAÇÃO DE CORS (IMPORTANTE PARA O REACT) ---
# Isso permite que o Front-end (porta 5173) converse com o Back-end (porta 8000)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONEXÃO DOS MÓDULOS (ROUTERS) ---
app.include_router(auth.router)
app.include_router(guests.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(products.router)
app.include_router(finance.router)   # <--- NOVO
app.include_router(settings.router)  # <--- NOVO
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(events.router)
app.include_router(webhook_whatsapp.router)

# Serve PDF reports
os.makedirs("reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

@app.get("/")
def root():
    return {"message": "Sistema Modular Operacional! 🚀"}

@app.get("/_diag")
def _diag():
    return {"exe": sys.executable, "path": sys.path}
