"""
schemas/admin_state.py — Estado compartilhado do sistema administrativo da Ana.
Definido em arquivo separado para evitar imports circulares entre
admin_orchestrator.py e os admin_specialists/.
EXCLUSIVO do sistema Admin. NÃO compartilha nada com o customer agent.
"""
from typing import Optional, Dict, Any, List, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AdminState(TypedDict):
    """
    Estado central do grafo administrativo da Ana (Orquestradora).
    Viaja entre o AdminOrchestrator e todos os Agentes Especialistas Admin.
    """
    # Histórico de mensagens acumulativo (LangGraph gerencia automaticamente)
    messages: Annotated[List[BaseMessage], add_messages]
    # Identidade da sessão
    tenant_id: int
    session_id: str
    # Destino do roteamento determinado pelo orquestrador
    route: Optional[str]  # "operacoes" | "reservas" | "financeiro" | "direto"
    # Contexto operacional extraído da mensagem (enriquece o especialista)
    target_room_id: Optional[str]      # Quarto mencionado pelo usuário
    target_booking_id: Optional[int]   # ID de reserva mencionado
    target_guest_id: Optional[int]     # ID de hóspede em foco
    current_task: Optional[str]        # Tarefa em andamento (ex: "checkout_preview")
    task_context: Optional[Dict[str, Any]]  # Dados extras para a tarefa
