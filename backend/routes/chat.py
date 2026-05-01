from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time
from collections import defaultdict

# Imports corrigidos para a estrutura do projeto
from database import SessionLocal, set_tenant_context
from agents.state_manager import StateManager
from agents.supervisor_agent import SupervisorAgent
import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class ChatRequest(BaseModel):
    """Requisição de chat do cliente."""
    message: str = Field(..., min_length=1, max_length=5000, description="Mensagem do usuário")
    session_id: str = Field(..., description="ID único da sessão")
    tenant_id: int = Field(..., description="ID do tenant (pousada)")

class ChatResponse(BaseModel):
    """Resposta do chat para o cliente."""
    response: str = Field(..., description="Resposta do agente")
    state: str = Field(..., description="Estado atual da sessão (DISCOVERY, VALIDATION, etc)")
    specialist: str = Field(..., description="Specialist que processou a mensagem")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto da sessão")
    next_action: Optional[str] = Field(None, description="Próxima ação sugerida")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, session_id: str) -> bool:
        now = time.time()
        self.requests[session_id] = [r for r in self.requests[session_id] if now - r < self.window_seconds]
        if len(self.requests[session_id]) >= self.max_requests:
            return False
        self.requests[session_id].append(now)
        return True

rate_limiter = RateLimiter()

# ============================================================================
# DEPENDENCIAS
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def validate_tenant(tenant_id: int, db: Session) -> models.Tenant:
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} não encontrado")
    return tenant

def validate_session(session_id: str, tenant_id: int, db: Session) -> Any:
    set_tenant_context(db, tenant_id)
    state_manager = StateManager(tenant_id)
    session_state = state_manager.load_session(session_id)
    return session_state

# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/api/v1/chat", tags=["Chat V1 Agentic"])

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db)
) -> ChatResponse:
    try:
        logger.info(f"[AI_LOG] V1: Mensagem para tenant {request.tenant_id}, sessão {request.session_id}")
        
        # 1. Validar tenant
        validate_tenant(request.tenant_id, db)
        
        # 2. Validar rate limit
        if not rate_limiter.is_allowed(request.session_id):
            raise HTTPException(status_code=429, detail="Rate limit excedido")
        
        # 3. Validar sessão e carregar contexto fresco
        state_manager = StateManager(request.tenant_id)
        session_data = state_manager.load_session(request.session_id)
        context_from_db = session_data.get('context', {}) if session_data else {}
        
        # 4. Chamar SupervisorAgent (Orquestrador Único)
        supervisor = SupervisorAgent(request.tenant_id)
        result = await supervisor.process(
            message=request.message,
            session_id=request.session_id,
            context=context_from_db
        )
        
        # 5. Retornar resposta consolidada
        return ChatResponse(
            response=result['response'],
            state=result['state'],
            specialist=result['specialist'],
            context=result.get('context', {}),
            next_action=_suggest_next_action(result['state'])
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AI_LOG] Erro V1 Chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do agente")

@router.get("/session/{session_id}")
async def get_session_state(
    session_id: str,
    tenant_id: int,
    db: Session = Depends(get_db)
):
    validate_tenant(tenant_id, db)
    set_tenant_context(db, tenant_id)
    state_manager = StateManager(tenant_id)
    session_state = state_manager.load_session(session_id)
    if not session_state:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    
    state, history = state_manager.get_state_and_history(session_id)
    return {
        'session_id': session_id,
        'current_state': state,
        'context': session_state.get_context(),
        'history': history,
        'updated_at': datetime.utcnow().isoformat()
    }

@router.get("/health")
async def health_check():
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}

def _suggest_next_action(current_state: str) -> str:
    suggestions = {
        'DISCOVERY': 'Informe as datas e o número de pessoas',
        'VALIDATION': 'Confirme os dados dos acompanhantes',
        'PAYMENT': 'Proceda com o pagamento PIX',
        'COMPLETE': 'Reserva finalizada!'
    }
    return suggestions.get(current_state, 'Próxima etapa...')
