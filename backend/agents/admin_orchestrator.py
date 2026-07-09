"""
AdminOrchestrator — Orquestrador Central da Ana (Assistente Holográfica).
Recebe a mensagem do usuário, determina a intenção e delega para o especialista adequado.
Arquitetura LangGraph com FSM (Finite State Machine) e estado compartilhado.
COMPLETAMENTE SEPARADO do SupervisorAgent (customer agent).
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Estado compartilhado — definido em schemas/ para evitar import circular
from agents.schemas.admin_state import AdminState

logger = logging.getLogger("ADMIN.ORCHESTRATOR")

# =============================================================================
# ORQUESTRADOR PRINCIPAL
# =============================================================================

class AdminOrchestrator:
    """
    Orquestrador Central da Ana.
    Analisa a intenção do gerente e delega para o especialista certo.
    """

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def _classify_intent(self, message: str) -> str:
        """
        Classifica a intenção da mensagem do gerente.
        Retorna o nome do especialista a acionar.
        """
        msg = message.lower()

        # ── OPERAÇÕES (quartos, consumo, limpeza, checkout) ────────────────
        operacoes_keywords = [
            "quarto", "limpeza", "manutenção", "manutencao", "limpar", "limpo",
            "pronto", "liberar", "consumo", "consumir", "adicionar", "lançar",
            "cerveja", "refrigerante", "bebida", "produto", "item", "conta",
            "checkout", "check-out", "saída do hóspede", "fechar conta",
            "extrato do quarto", "hóspede do quarto", "quem está no quarto",
            "status do quarto", "quartos disponíveis", "quartos em"
        ]
        if any(kw in msg for kw in operacoes_keywords):
            return "operacoes"

        # ── FINANCEIRO (relatórios, despesas, estoque, analytics) ──────────
        financeiro_keywords = [
            "relatório", "relatorio", "financeiro", "finanças", "financas",
            "faturamento", "receita", "despesa", "gasto", "conta a pagar",
            "pdf", "documento", "estoque", "inventário", "inventario",
            "compras", "lista de compras", "produto", "produto no estoque",
            "caixa", "fechamento de caixa", "analytics", "análise", "analise",
            "energia", "água", "água", "salário", "fornecedor", "kpi"
        ]
        if any(kw in msg for kw in financeiro_keywords):
            return "financeiro"

        # ── RESERVAS (booking, hóspede, disponibilidade, pagamento) ────────
        reservas_keywords = [
            "reserva", "reservas", "reservar", "booking", "pendente", "pendentes",
            "confirmada", "confirmadas", "ativa", "ativas", "hóspede", "hospede",
            "check-in", "checkin", "check in", "disponibilidade", "disponível",
            "disponíveis", "pagamento", "pagar", "pix", "confirma pagamento",
            "nova reserva", "criar reserva", "cancelar reserva", "quantas reservas",
            "evento", "eventos", "canção nova", "calendário", "calendario"
        ]
        if any(kw in msg for kw in reservas_keywords):
            return "reservas"

        # Default: Ana responde diretamente para perguntas gerais/ações rápidas
        return "direto"

    def _extract_context_from_message(self, message: str) -> Dict[str, Any]:
        """Extrai entidades contextuais da mensagem para enriquecer o estado."""
        import re
        context = {}

        # Extrai número de quarto (ex: "quarto 101", "101")
        room_match = re.search(r'\b(?:quarto|qto|room|nº|#)?\s*(\d{2,3})\b', message, re.IGNORECASE)
        if room_match:
            context["target_room_id"] = room_match.group(1)

        # Extrai ID de reserva (ex: "reserva 47", "#47")
        booking_match = re.search(r'\b(?:reserva|booking|#)\s*(\d+)\b', message, re.IGNORECASE)
        if booking_match:
            context["target_booking_id"] = int(booking_match.group(1))

        return context

    async def process(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Ponto de entrada principal. Processa uma mensagem do gerente.
        Retorna {"response": str, "route_used": str, "session_id": str}
        """
        logger.info(f"[ORCHESTRATOR] Processando: '{message[:60]}...' | session={session_id}")

        # 1. Classificar intenção
        route = self._classify_intent(message)
        logger.info(f"[ORCHESTRATOR] Rota determinada: {route}")

        # 2. Extrair contexto da mensagem
        extracted = self._extract_context_from_message(message)

        # 3. Carregar histórico de mensagens do banco (últimas 10)
        from database import SessionLocal, set_tenant_context
        import models
        db = SessionLocal()
        set_tenant_context(db, self.tenant_id)
        db_msgs = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == session_id,
            models.ChatMessage.tenant_id == self.tenant_id
        ).order_by(models.ChatMessage.created_at.asc()).all()
        db.close()

        history = []
        for m in db_msgs[-10:]:
            if m.role == "user":
                history.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                history.append(AIMessage(content=m.content))
        history.append(HumanMessage(content=message))

        # 4. Montar estado inicial
        initial_state: AdminState = {
            "messages": history,
            "tenant_id": self.tenant_id,
            "session_id": session_id,
            "route": route,
            "target_room_id": extracted.get("target_room_id"),
            "target_booking_id": extracted.get("target_booking_id"),
            "target_guest_id": None,
            "current_task": None,
            "task_context": {},
        }

        # 5. Delegar para especialista
        response_text = ""
        try:
            if route == "operacoes":
                from agents.admin_specialists.operacoes_agent import build_operacoes_graph
                graph = build_operacoes_graph(self.tenant_id)
                final_state = await graph.ainvoke(initial_state)

            elif route == "reservas":
                from agents.admin_specialists.reservas_agent import build_reservas_admin_graph
                graph = build_reservas_admin_graph(self.tenant_id)
                final_state = await graph.ainvoke(initial_state)

            elif route == "financeiro":
                from agents.admin_specialists.financeiro_agent import build_financeiro_graph
                graph = build_financeiro_graph(self.tenant_id)
                final_state = await graph.ainvoke(initial_state)

            else:
                # Resposta direta da Ana para perguntas gerais
                final_state = await self._handle_direct(initial_state)

            # 6. Extrair resposta final
            response_text = self._extract_response(final_state)

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Erro na delegação: {e}", exc_info=True)
            response_text = "Encontrei uma dificuldade técnica ao processar sua solicitação. Pode tentar novamente?"

        # 7. Sanitizar links Markdown
        import re
        response_text = re.sub(
            r'\[(.*?)\]\(\s*(.*?)\s*\)',
            lambda m: f"[{m.group(1)}]({m.group(2).replace(' ', '')})",
            response_text
        )

        # 8. Persistir mensagens no banco
        db = SessionLocal()
        set_tenant_context(db, self.tenant_id)
        db.add(models.ChatMessage(
            tenant_id=self.tenant_id,
            session_id=session_id,
            role="assistant",
            content=response_text
        ))
        db.commit()
        db.close()

        logger.info(f"[ORCHESTRATOR] Resposta gerada ({len(response_text)} chars) via rota '{route}'")
        return {"response": response_text, "route_used": route, "session_id": session_id}

    async def _handle_direct(self, state: AdminState) -> AdminState:
        """Responde diretamente sem delegar, para perguntas gerais sobre o sistema."""
        google_key = os.getenv("GOOGLE_API_KEY")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.2)

        sys_msg = SystemMessage(content=f"""Você é a Ana, assistente holográfica gerencial da pousada.
Hoje é {datetime.now().strftime('%A, %d de %B de %Y')}.
Responda perguntas gerais de forma direta, profissional e amigável.
Se o usuário pedir algo que requer dados do sistema (quartos, reservas, relatórios),
diga que pode ajudar e peça mais detalhes.
Responda em português brasileiro.""")

        response = await llm.ainvoke([sys_msg] + state["messages"])
        return {**state, "messages": state["messages"] + [response]}

    def _extract_response(self, final_state: AdminState) -> str:
        """Extrai o texto da última mensagem de IA no estado."""
        for m in reversed(final_state["messages"]):
            if isinstance(m, AIMessage) and m.content:
                content = m.content
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and "text" in c
                    ).strip()
                if content and not content.startswith("{"):
                    return content
        return "Solicitação processada. Como posso ajudar mais?"


# =============================================================================
# FUNÇÃO DE CONVENIÊNCIA — Ponto de Entrada para os Routers HTTP
# =============================================================================

async def handle_admin_query_v2(
    message: str,
    history: list,
    tenant_id: int,
    session_id: str = "default_admin"
) -> Dict[str, Any]:
    """
    Substitui o handle_admin_query legado.
    Compatível com o router de /chat/admin.
    """
    orchestrator = AdminOrchestrator(tenant_id)
    return await orchestrator.process(message, session_id)
