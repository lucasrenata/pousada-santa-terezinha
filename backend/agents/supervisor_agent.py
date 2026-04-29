from typing import Dict, Any, Optional, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import os
import asyncio

from agents.base_specialist import BaseSpecialist
from agents.graph import get_pousada_brain
from agents.state_manager import StateManager
import models
from database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupervisorAgent(BaseSpecialist):
    """
    Supervisor Agent (ORQUESTRADOR LANGGRAPH):
    Ponto de entrada único para o Grafo de Atendimento.
    """
    
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "SUPERVISOR")
        self.state_manager = StateManager(tenant_id)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call_llm(self, messages: list) -> str:
        """Chama LLM com retry automático."""
        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"[SUPERVISOR_LOG] Erro LLM: {str(e)}")
            raise
    
    async def decide_next_specialist(self, current_state: str, user_message: str, context: Dict[str, Any]) -> str:
        """
        Decide qual especialista deve lidar com a mensagem, considerando dados críticos.
        """
        prompt = f"""
Você é um orquestrador de agentes de IA para uma pousada.
Estado atual: {current_state}
Mensagem do usuário: {user_message}

Decida qual especialista chamar:
- "discovery": buscas, preços, disponibilidade.
- "validation": dados pessoais (CPF, Nome), acompanhantes.
- "confirmation": revisão de resumo, confirmação final.
- "payment": pagamento, QR Code, avisar que pagou.

Responda APENAS com o nome do specialist em minúsculo.
"""
        response = await self._call_llm([HumanMessage(content=prompt)])
        specialist = response.strip().lower()
        
        # Camada 3: Reforço no Supervisor (Mente Central)
        # Se estamos tentando ir para PAYMENT ou CONFIRMATION sem dados críticos, força DISCOVERY
        # Camada 3: Reforço no Supervisor (Mente Central)
        # Se estamos tentando ir para PAYMENT ou CONFIRMATION sem dados críticos, força DISCOVERY
        # A MENOS QUE a mensagem atual pareça conter esses dados.
        if specialist in ["payment", "confirmation"]:
            has_dates = context.get('check_in') and context.get('check_out')
            # Se não tem no contexto, mas o usuário parace estar informando (ex: "dia 20")
            # Deixamos o fluxo seguir para que o Guardian extraia e o Especialista processe.
            likely_providing_info = any(m in user_message.lower() for m in ["dia", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro", "quarto", "pessoa", "sozinho"])
            
            if not has_dates and not likely_providing_info:
                logger.warning(f"[SUPERVISOR_LOG] Dados críticos faltando para {specialist.upper()}, voltando para DISCOVERY")
                return "discovery"
        
        valid = ["discovery", "validation", "confirmation", "payment"]
        if specialist not in valid:
            state_map = {"DISCOVERY": "discovery", "VALIDATION": "validation", "CONFIRMATION": "confirmation", "PAYMENT": "payment"}
            specialist = state_map.get(current_state, "discovery")
        
        return specialist
    
    async def process(self, message: str, session_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ponto de entrada para o processamento de mensagens via LangGraph.
        Agora suporta Janela Deslizante de Histórico via ChatMessage.
        """
        db = self._get_db_session()
        try:
            # 1. Carregar Histórico do Banco (Últimas 10 mensagens)
            db_history = db.query(models.ChatMessage).filter(
                models.ChatMessage.session_id == session_id
            ).order_by(models.ChatMessage.created_at.desc()).limit(10).all()
            
            db_history.reverse()
            
            history = []
            for msg in db_history:
                if msg.role == 'user':
                    history.append(HumanMessage(content=msg.content))
                else:
                    history.append(AIMessage(content=msg.content))

            # 2. Salvar Mensagem Atual do Usuário
            user_msg_record = models.ChatMessage(
                session_id=session_id, role='user', content=message, tenant_id=self.tenant_id
            )
            db.add(user_msg_record)
            db.commit()

            # 3. Carregar/Garantir Contexto

            context_data = self.state_manager.load_session(session_id)
            context = context_data.get('context', {}) if context_data else (context or {})
            current_state = context_data.get('current_state', 'DISCOVERY') if context_data else 'DISCOVERY'

            # 4. Roteamento
            next_specialist = await self.decide_next_specialist(current_state, message, context)
            logger.info(f"[SUPERVISOR_LOG] Roteando para: {next_specialist}")

            # 5. Execução via LangGraph (COM CHECKPOINT)
            brain = await get_pousada_brain()
            config = {"configurable": {"thread_id": session_id}}
            
            initial_state = {
                "message": message,
                "session_id": session_id,
                "tenant_id": self.tenant_id,
                "context": context,
                "next_specialist": next_specialist,
                "current_state": current_state,
                "history": history
            }
            
            final_state = await brain.ainvoke(initial_state, config=config)
            
            # 6. Salvar Resposta da IA no Histórico
            response_text = final_state.get("response", "Não entendi.")
            ai_msg_record = models.ChatMessage(
                session_id=session_id, role='assistant', content=response_text, tenant_id=self.tenant_id
            )
            db.add(ai_msg_record)
            db.commit()
            
            # 7. Persistência Final do Estado Atômico (Sincronizado)
            new_context = final_state.get("context", {})
            new_state = final_state.get("current_state", next_specialist)
            
            # Garante que o estado atualizado seja salvo na memória persistente do tenant
            context_to_save = {**new_context, "current_state": new_state}
            self.state_manager.update_state(session_id, context_to_save)
            
            # 8. Formatar Resposta Consolidada
            return {
                "response": response_text,
                "state": new_state,
                "specialist": next_specialist,
                "context": context_to_save
            }

        except Exception as e:
            logger.error(f"[SUPERVISOR_LOG] Erro crítico no Grafo: {str(e)}", exc_info=True)
            return {
                'response': "Desculpe, tive um problema técnico ao processar sua solicitação.",
                'state': 'ERROR',
                'specialist': 'supervisor',
                'context': context or {}
            }
        finally:
            db.close()
