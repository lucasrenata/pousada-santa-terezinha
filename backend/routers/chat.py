from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, set_tenant_context
from .auth import get_current_staff, get_current_admin
from pydantic import BaseModel
import os
import json
from openai import OpenAI
from typing import List, Optional, Any

import models
from datetime import datetime
import logging

logger = logging.getLogger("CHAT_ROUTER")

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

async def process_debounced_messages(session_id: str, tenant_id: int, job_id: str):
    """Processa o acúmulo de mensagens após o delay de debouncing."""
    from agents.supervisor_agent import SupervisorAgent
    from database import SessionLocal
    
    buffer_key = f"chat:buffer:{session_id}"
    lock_key = f"chat:lock:{session_id}"
    
    # 1. Espera o usuário terminar de digitar (janela de 2.5s)
    await asyncio.sleep(2.5)
    
    # 2. Coleta tudo o que foi acumulado
    msgs_bytes = redis_conn.lrange(buffer_key, 0, -1)
    redis_conn.delete(buffer_key)
    redis_conn.delete(lock_key) # Libera para o próximo grupo
    
    if not msgs_bytes:
        return

    full_message = " ".join([m.decode('utf-8', errors='ignore') for m in msgs_bytes])
    
    # 3. Processa com a IA
    try:
        supervisor = SupervisorAgent(tenant_id)
        result = await supervisor.process(full_message, session_id)
        
        # 4. Salva o resultado no Redis para o Polling do Frontend
        job_data = {
            "status": "finished",
            "result": json.dumps(result)
        }
        redis_conn.hset(f"rq:job:{job_id}", mapping=job_data)
        redis_conn.expire(f"rq:job:{job_id}", 600) # 10 min de expiração
    except Exception as e:
        logger.error(f"Erro no processamento debounced: {e}")
        redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "failed", "error": str(e)})

@router.post("/customer")
async def chat_customer(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Processa a IA com concatenação de mensagens (Debouncing) via Redis."""
    set_tenant_context(db, request.tenant_id)
    
    # 1. Salva no histórico imediatamente
    save_message(request.session_id, "user", request.message, request.tenant_id, db)
    
    buffer_key = f"chat:buffer:{request.session_id}"
    lock_key = f"chat:lock:{request.session_id}"
    job_id_key = f"chat:active_job:{request.session_id}"
    
    # Adiciona a mensagem atual ao buffer
    redis_conn.rpush(buffer_key, request.message)
    redis_conn.expire(buffer_key, 60)
    
    # Tenta obter ou criar um Job ID para este grupo
    import hashlib, time
    job_id = redis_conn.get(job_id_key)
    if job_id:
        job_id = job_id.decode()
    else:
        job_id = f"sync_{hashlib.md5(request.session_id.encode()).hexdigest()}_{int(time.time())}"
        redis_conn.setex(job_id_key, 30, job_id)

    # Tenta ser o "Líder" (quem vai processar o bloco)
    if redis_conn.set(lock_key, "1", ex=20, nx=True):
        # Sou o líder. Vou avisar o Redis que já estou processando para evitar 404 no polling
        redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "processing"})
        redis_conn.expire(f"rq:job:{job_id}", 300)

        try:
            # 1. Espera o usuário terminar de digitar (janela de 2.5s)
            await asyncio.sleep(2.5)
            
            # 2. Coleta tudo o que foi acumulado no Redis
            msgs_bytes = redis_conn.lrange(buffer_key, 0, -1)
            redis_conn.delete(buffer_key)
            redis_conn.delete(lock_key)
            redis_conn.delete(job_id_key)
            
            if not msgs_bytes:
                return {"status": "empty"}

            full_message = " ".join([m.decode('utf-8', errors='ignore') for m in msgs_bytes])
            
            # 3. Processa com a IA de forma síncrona (para esta request)
            from agents.supervisor_agent import SupervisorAgent
            supervisor = SupervisorAgent(request.tenant_id)
            result = await supervisor.process(full_message, request.session_id)
            
            # Atualiza o Redis para quem estiver no polling
            redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "finished", "result": json.dumps(result)})

            return {
                "job_id": job_id,
                "status": "finished",
                "result": result
            }
        except Exception as e:
            logger.error(f"Erro no processamento síncrono: {e}")
            redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "failed", "error": str(e)})
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(e)
            }
    else:
        # Sou um seguidor, apenas avisamos o frontend que a mensagem foi agrupada
        # Também garantimos que o job_id esteja no Redis se ainda não estiver
        if not redis_conn.exists(f"rq:job:{job_id}"):
            redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "processing"})
            redis_conn.expire(f"rq:job:{job_id}", 300)

        return {
            "job_id": job_id,
            "status": "buffering",
            "message": "Mensagem agrupada."
        }

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Endpoint de Polling compatível com Jobs Sync e Async."""
    # Primeiro verifica se é um Job Síncrono (Fake Job)
    if job_id.startswith("sync_") or job_id.startswith("admin_"):
        data = redis_conn.hgetall(f"rq:job:{job_id}")
        if data:
            status = data.get(b"status", b"finished").decode()
            result_raw = data.get(b"result")
            result = json.loads(result_raw.decode()) if result_raw else {}
            return {
                "status": status,
                "result": result
            }
        else:
            # Se é um job sync mas ainda não tem dados, ele está em processamento
            return {"status": "processing"}
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        # Se não encontrou no RQ mas o ID é nosso, consideramos processando
        return {"status": "processing"}
    
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
async def chat_admin(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    """Migra o Admin para processamento direto no backend (Background Task)."""
    tid = current_admin.tenant_id
    
    # Guard: se o tenant_id for None (sessão expirada/inválida), retorna 401
    if tid is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")
    
    set_tenant_context(db, tid)
    
    # --- TRAVA DE IDEMPOTÊNCIA (ANTI-DUPLICIDADE) ---
    import hashlib, time
    message_hash = hashlib.md5(f"{request.session_id}:{request.message}".encode()).hexdigest()
    idempotency_key = f"admin:lock:{message_hash}"
    
    existing_job = redis_conn.get(idempotency_key)
    if existing_job:
        logger.info(f"[CHAT_ADMIN] Reenvio detectado para msg hash {message_hash}. Reaproveitando job {existing_job.decode()}")
        return {"job_id": existing_job.decode(), "status": "processing"}

    # 1. Salva a mensagem do usuário imediatamente
    save_message(request.session_id, "user", request.message, tid, db)
    
    # 2. Busca o histórico
    history = await get_db_history(request.session_id, db, tid)
    
    # 3. Cria um Job ID (Desta vez usamos o hash para ser estável se o lock expirar muito rápido)
    job_id = f"admin_{message_hash}_{int(time.time())}"
    
    # Registra o lock por 60 segundos
    redis_conn.setex(idempotency_key, 60, job_id)
    
    # Função interna para processar sem travar a requisição HTTP
    async def run_admin_direct():
        from agents.admin_agent import handle_admin_query
        try:
            # handle_admin_query já é async e recebe sua própria session se necessário, 
            # mas vamos passar a session principal se ele exigir.
            # Nota: handle_admin_query em admin_agent.py espera (message, history, db, tenant_id, session_id)
            result = await handle_admin_query(request.message, history[:-1], db, tid, request.session_id)
            
            if result and result.get("response"):
                save_message(request.session_id, "assistant", result["response"], tid, db)
            
            redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "finished", "result": json.dumps(result)})
        except Exception as e:
            logger.error(f"Erro no processamento Admin: {e}")
            redis_conn.hset(f"rq:job:{job_id}", mapping={"status": "failed", "error": str(e)})

    background_tasks.add_task(run_admin_direct)
    
    return {"job_id": job_id, "status": "processing"}

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
