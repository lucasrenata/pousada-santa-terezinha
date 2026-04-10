from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from database import get_db
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
    chat_history: List[dict] = []

async def get_db_history(session_id: str, db: Session):
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    # Filtramos mensagens vazias que podem ter vindo de tool_calls incompletos na persistência
    return [{"role": m.role, "content": m.content} for m in messages if m.content and m.content.strip()]

def save_message(session_id: str, role: str, content: str, db: Session):
    msg = models.ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()

@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, db: Session = Depends(get_db)):
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

@router.post("/customer")
async def chat_customer(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. Salva mensagem do usuário
    save_message(request.session_id, "user", request.message, db)
    
    # 2. Busca histórico completo do banco (Fonte da Verdade)
    history = await get_db_history(request.session_id, db)
    
    # 3. Importação tardia do agente
    from agents.customer_agent import handle_customer_query
    
    # Chamamos o agente (ele já recebe o histórico do banco)
    result = await handle_customer_query(request.message, history[:-1], db) # Passamos histórico sem a mensagem atual (agente adiciona ela)
    
    # 4. Salva resposta da IA
    save_message(request.session_id, "assistant", result["response"], db)
    
    return result

@router.post("/admin")
async def chat_admin(request: ChatRequest, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    save_message(request.session_id, "user", request.message, db)
    history = await get_db_history(request.session_id, db)
    
    from agents.admin_agent import handle_admin_query
    result = await handle_admin_query(request.message, history[:-1], db)
    
    save_message(request.session_id, "assistant", result["response"], db)
    
    return result

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
