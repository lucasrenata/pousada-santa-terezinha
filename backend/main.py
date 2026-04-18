from pathlib import Path
from dotenv import load_dotenv
import os

# Carrega variáveis de ambiente antes de qualquer outro import que dependa delas
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=True)

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine
import models
from routers import auth, guests, rooms, bookings, products, finance, settings, payments, admin, chat, events, webhook_whatsapp, business_rules, superadmin, pdv
from routes.chat import router as chat_v1_router
from routes.webhooks import router as webhooks_router
import sys

# Tabelas no banco agora são gerenciadas via Alembic Migrations.
# models.Base.metadata.create_all(bind=engine)

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
app.include_router(auth.router, prefix="/auth")
app.include_router(guests.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(products.router)
app.include_router(finance.router)
app.include_router(settings.router)
app.include_router(business_rules.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(chat_v1_router)
app.include_router(events.router)
app.include_router(webhook_whatsapp.router)
app.include_router(webhooks_router)
app.include_router(superadmin.router)
app.include_router(pdv.router)

# Serve arquivos estáticos (Uploads de comprovantes, etc)
os.makedirs("static/uploads/receipts", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve PDF reports with auto-delete after download
os.makedirs("reports", exist_ok=True)

@app.get("/reports/{filename}")
async def get_report(filename: str, background_tasks: BackgroundTasks):
    file_path = f"reports/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Relatório não encontrado ou já expirado.")
    
    def remove_file(path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Erro ao deletar relatório {path}: {e}")

    background_tasks.add_task(remove_file, file_path)
    return FileResponse(file_path, media_type='application/pdf', filename=filename)

@app.get("/")
def root():
    return {"message": "Sistema Modular Operacional! 🚀"}

@app.get("/_diag")
def _diag():
    return {"exe": sys.executable, "path": sys.path}
