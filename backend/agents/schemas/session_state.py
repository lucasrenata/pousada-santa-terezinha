from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# =============================================================================
# ESTADO COMPARTILHADO DO SISTEMA DE ATENDIMENTO (MULTI-AGENTES)
# Viaja entre o Supervisor e todos os Sub-Agentes de forma imutável/acumulativa.
# =============================================================================
class HotelBookingState(TypedDict):
    """Estado central do grafo de atendimento ao hóspede."""
    # Histórico de mensagens (LangGraph accumula automaticamente com add_messages)
    messages: Annotated[List[BaseMessage], add_messages]
    # Etapa do funil de atendimento (controlada pelo Supervisor)
    etapa: str  # "SAUDACAO" | "COTACAO" | "IDENTIFICACAO" | "CONFIRMACAO" | "PAGAMENTO" | "CONCLUIDO"
    # Identidade da sessão
    tenant_id: int
    session_id: str
    # Dados coletados progressivamente durante a conversa
    check_in: Optional[str]
    check_out: Optional[str]
    # REGRA: group_size inclui o hóspede principal. Acompanhantes = group_size - 1.
    group_size: int
    room_id: Optional[str]
    guest_id: Optional[int]
    booking_id: Optional[int]
    # Lista de acompanhantes: [{"name": str, "age": int}]
    # O hóspede principal NÃO entra aqui — ele já está no guest_id
    companions: Optional[List[Dict[str, Any]]]
    # CPF coletado (antes de ser guest_id)
    cpf: Optional[str]


# =============================================================================
# MODELO LEGADO (mantido para compatibilidade com StateManager)
# =============================================================================
class SessionState(BaseModel):
    """Modelo Pydantic para manipulação em tempo de execução via StateManager."""
    user_id: Optional[str] = None
    current_step: str = 'initial'
    booking_details: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    last_query: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def current_state(self) -> str:
        return self.current_step

    def get_context(self) -> Dict[str, Any]:
        return self.model_dump()
