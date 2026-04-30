import logging
from typing import Dict, Any
from database import SessionLocal, set_tenant_context
import models
from agents.graph import get_pousada_brain
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)

class SupervisorAgent:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    async def process(self, message: str, session_id: str) -> Dict[str, Any]:
        from agents.state_manager import StateManager
        from agents.reviewer_agent import ReviewerAgent
        from agents.customer_agent import handle_customer_query
        
        sm = StateManager(self.tenant_id)
        reviewer = ReviewerAgent(self.tenant_id)
        
        try:
            # 1. Carregar Histórico real do banco
            db_history = []
            db = SessionLocal()
            try:
                set_tenant_context(db, self.tenant_id)
                messages = db.query(models.ChatMessage).filter(
                    models.ChatMessage.session_id == session_id,
                    models.ChatMessage.tenant_id == self.tenant_id
                ).order_by(models.ChatMessage.created_at.asc()).all()
                
                # Formato simples para o Revisor
                simple_history = [{"role": m.role, "content": m.content} for m in messages]
                
                # 2. CHAMAR O AGENTE PRINCIPAL (A PONTE)
                # Removemos o Revisor para ganhar velocidade instantânea.
                result = await handle_customer_query(message, simple_history, db, self.tenant_id, session_id)
                
                # 4. PERSISTÊNCIA DA RESPOSTA DA IA
                # A mensagem do usuário agora é salva imediatamente pelo Router (chat.py)
                db.add(models.ChatMessage(tenant_id=self.tenant_id, session_id=session_id, role="assistant", content=result["response"]))
                db.commit()
                
                return {
                    "response": result["response"],
                    "session_id": session_id,
                    "specialist": "customer_agent"
                }
                
            finally:
                db.close()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "response": "Desculpe, tive um problema técnico na minha recepção. Pode repetir?",
                "session_id": session_id
            }
