from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from .auth import get_current_staff, get_current_admin
from pydantic import BaseModel
import os
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
