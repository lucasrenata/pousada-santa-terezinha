from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request
from sqlalchemy.orm import Session
from database import get_db, set_tenant_context
from .auth import get_current_staff, get_current_admin
from pydantic import BaseModel
import os
from openai import OpenAI
from typing import List

import models
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["AI Chat Agents"])

class ChatRequest(BaseModel):
    message: str
    session_id: str # Obrigatório para persistência
    tenant_id: int # ID da Pousada
    chat_history: List[dict] = []

async def get_db_history(session_id: str, db: Session, tenant_id: int):
    # O isolamento RLS já deve filtrar, mas passamos tenant_id por segurança/clareza
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.tenant_id == tenant_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    # Filtramos mensagens vazias que podem ter vindo de tool_calls incompletos na persistência
    return [{"role": m.role, "content": m.content} for m in messages if m.content and m.content.strip()]

def save_message(session_id: str, role: str, content: str, tenant_id: int, db: Session):
    set_tenant_context(db, tenant_id)
    msg = models.ChatMessage(session_id=session_id, role=role, content=content, tenant_id=tenant_id)
    db.add(msg)
    db.commit()

@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, tenant_id: int, db: Session = Depends(get_db)):
    set_tenant_context(db, tenant_id)
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at
        } for m in messages
    ]

import asyncio
from redis import Redis
from rq import Queue
from rq.job import Job

# Configuração do Redis e Fila
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
redis_conn = Redis.from_url(redis_url)
q = Queue('default', connection=redis_conn)

def run_agent_task(message: str, session_id: str, tenant_id: int):
    """Função que será executada pelo Worker (Sync wrapper para código Async)"""
    from agents.supervisor_agent import SupervisorAgent
    # Criamos um novo loop se necessário (dentro do worker)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        supervisor = SupervisorAgent(tenant_id)
        return loop.run_until_complete(supervisor.process(message, session_id))
    finally:
        loop.close()

@router.post("/customer")
async def chat_customer(request: ChatRequest, db: Session = Depends(get_db)):
    """Recebe a mensagem, aplica trava de idempotência e delega para o Worker."""
    set_tenant_context(db, request.tenant_id)
    
    # --- TRAVA DE IDEMPOTÊNCIA (Diretriz do Arquiteto) ---
    import hashlib
    msg_hash = hashlib.md5(f"{request.session_id}:{request.message}".encode()).hexdigest()
    lock_key = f"lock:chat:{msg_hash}"
    
    if redis_conn.get(lock_key):
        return {"status": "processing", "detail": "Mensagem já está sendo processada. Aguarde."}
    
    # Trava por 10 segundos (tempo suficiente para o worker começar)
    redis_conn.setex(lock_key, 10, "1")
    
    # Salva a mensagem do usuário imediatamente para o histórico
    save_message(request.session_id, "user", request.message, request.tenant_id, db)
    
    job = q.enqueue(
        run_agent_task, 
        request.message, 
        request.session_id, 
        request.tenant_id,
        job_timeout='2m'
    )
    return {"job_id": job.id, "status": "queued"}

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Endpoint de Polling para verificar o status e o resultado do agente."""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job.is_finished:
        return {
            "status": "finished",
            "result": job.result
        }
    elif job.is_failed:
        return {
            "status": "failed",
            "error": str(job.exc_info)
        }
    else:
        return {
            "status": "processing"
        }

def run_admin_task(message: str, history: List[dict], tenant_id: int, session_id: str):
    """Função que será executada pelo Worker para o Agente Admin"""
    from agents.admin_agent import handle_admin_query
    from database import SessionLocal
    from routers.chat import save_message
    import asyncio
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = SessionLocal()
    try:
        from database import set_tenant_context
        set_tenant_context(db, tenant_id)
        result = loop.run_until_complete(handle_admin_query(message, history, db, tenant_id, session_id))
        
        # Salva a resposta do assistente no DB para o histórico
        if result and result.get("response"):
            save_message(session_id, "assistant", result["response"], tenant_id, db)
            
        return result
    finally:
        db.close()
        loop.close()

@router.post("/admin")
async def chat_admin(request: ChatRequest, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    # Captura antecipada para evitar ObjectDeletedError após commit
    tid = current_admin.tenant_id
    set_tenant_context(db, tid)
    
    # Salva a mensagem do usuário imediatamente para o histórico
    save_message(request.session_id, "user", request.message, tid, db)
    
    # Busca o histórico para passar ao worker
    history = await get_db_history(request.session_id, db, tid)
    
    # Dispara a tarefa assíncrona
    job = q.enqueue(
        run_admin_task,
        request.message,
        history[:-1], 
        tid,
        request.session_id, # Novo argumento
        job_timeout='5m'
    )
    
    return {"job_id": job.id, "status": "queued"}

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...), current_admin = Depends(get_current_admin)):
    """Transcreve áudio para texto usando OpenAI Whisper."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Chave da OpenAI não configurada.")

        # Criamos o cliente OpenAI
        client = OpenAI(api_key=api_key)

        # Lemos o conteúdo do áudio enviado
        audio_content = await audio.read()
        
        # O Whisper espera um arquivo, então usamos um truque de buffer com nome de arquivo
        from io import BytesIO
        audio_file = BytesIO(audio_content)
        audio_file.name = "audio.wav" # O nome ajuda a OpenAI a identificar o formato, mas webm/ogg também funcionam

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt" # Forçamos português para melhor precisão
        )

        return {"text": transcript.text}

    except Exception as e:
        print(f"Erro na transcrição: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar áudio: {str(e)}")
