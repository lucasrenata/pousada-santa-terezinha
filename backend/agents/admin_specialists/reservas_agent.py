"""
AgenteReservasAdmin — Especialista em Reservas e Ciclo de Hóspedes (lado ADMINISTRATIVO).
Responsabilidade: Buscar, consultar, criar e gerenciar reservas pelo lado do gerente.
COMPLETAMENTE SEPARADO do agente de atendimento ao hóspede (customer agent).
Não importa nada de customer_engine.py ou agents/specialists/.
"""
import os
import logging
from typing import List, Optional, Dict, Any

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.admin_state import AdminState

logger = logging.getLogger("ADMIN.RESERVAS")

RESERVAS_ADMIN_SYSTEM_PROMPT = """Você é o AGENTE DE RESERVAS ADMINISTRATIVO — especialista em gestão do ciclo completo de reservas da pousada.

## SUA FUNÇÃO
Dar ao gerente visibilidade e controle total sobre reservas: busca, consulta por categoria/status, criação administrativa e confirmações de pagamento.

## SUAS FERRAMENTAS
- `robot_booking_summary`: Visão panorâmica das reservas (quantas pendentes, ativas, concluídas, etc.)
- `robot_find_booking`: Localiza reservas específicas por CPF, nome do hóspede, número do quarto ou ID
- `robot_find_guest`: Verifica cadastro de hóspede por CPF ou nome
- `robot_check_availability`: Consulta disponibilidade e preços para datas e grupo
- `robot_book_admin`: Cria uma reserva diretamente (sem fluxo de venda ao hóspede)
- `robot_confirm_payment`: Dá baixa em pagamento de uma reserva
- `robot_get_payment_info`: Obtém dados de pagamento (PIX/link) de uma reserva
- `robot_event_intelligence`: Consulta o calendário de eventos regionais (Canção Nova, etc.) que afetam a demanda e os preços.

## REGRAS DE OURO
1. **Panorama primeiro**: Se o usuário perguntar "quantas reservas..." use robot_booking_summary.
2. **Localizar antes de agir**: Para confirmar pagamento ou verificar hóspede, use robot_find_booking primeiro.
3. **Seja um gerente**: Informe totais, percentuais e contexto. Ex: "Temos 5 reservas pendentes (2 vencem hoje)".
4. **Confirmação de ação destrutiva**: Antes de criar uma reserva, confirme os dados com o usuário.

## EXEMPLOS
- "Quantas reservas pendentes temos?" → robot_booking_summary(status="pendente")
- "Reservas de hoje" → robot_booking_summary(check_in_today=True)
- "Confirma pagamento da reserva 47" → robot_confirm_payment(booking_id=47)
- "Tem quarto disponível pro fim de semana?" → robot_check_availability(...)
- "Acha a reserva do João Silva" → robot_find_booking(name="João Silva")
- "Quais os eventos de maio?" → robot_event_intelligence(month=5)
- "Tem evento na Canção Nova semana que vem?" → robot_event_intelligence(search_query="Canção Nova")

Responda sempre em português brasileiro com postura gerencial: objetivo e com dados precisos.
"""


def build_reservas_admin_graph(tenant_id: int):
    """
    Constrói e retorna o grafo LangGraph do Agente de Reservas Administrativo.
    """
    from agents.admin_agent import (
        booking_summary_logic,
    )
    from agents.shared_tools import (
        find_booking_logic,
        find_guest_logic,
        availability_check_logic,
        booking_creation_logic,
        payment_info_logic,
        confirm_payment_logic,
        search_events_logic,
        event_listing_logic,
    )

    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # ── FERRAMENTAS RESTRITAS ──────────────────────────────────────────────────

    @tool
    def robot_booking_summary(
        status: Optional[str] = None,
        check_in_today: bool = False
    ) -> dict:
        """Panorama das reservas da pousada.
        status: filtra por 'pendente', 'confirmado', 'ativo', 'concluido' ou 'cancelado'.
        check_in_today=True: mostra check-ins previstos para hoje.
        Sem filtros: retorna contagem total por cada status."""
        return booking_summary_logic(tenant_id, status, check_in_today)

    @tool
    def robot_find_booking(
        cpf: str = "",
        name: str = "",
        room_id: str = "",
        booking_id: Optional[int] = None
    ) -> dict:
        """Localiza reservas por CPF do hóspede, nome, número do quarto ou ID direto da reserva.
        Retorna até 5 reservas mais recentes que correspondam."""
        return find_booking_logic(tenant_id, cpf, name, room_id, booking_id)

    @tool
    def robot_find_guest(cpf: str = "", name: str = "") -> dict:
        """Verifica se um hóspede existe no cadastro. Busca por CPF (exato) ou nome (parcial)."""
        return find_guest_logic(tenant_id, cpf, name)

    @tool
    def robot_check_availability(
        check_in: str,
        check_out: str,
        group_size: int = 1,
        ages: List[int] = []
    ) -> dict:
        """Consulta disponibilidade de quartos e preços para um período.
        check_in/check_out: formato DD/MM/YYYY ou YYYY-MM-DD.
        Retorna opções individuais e combinações inteligentes para grupos."""
        return availability_check_logic(tenant_id, check_in, check_out, group_size, ages)

    @tool
    def robot_book_admin(
        guest_id: int,
        room_id: str,
        check_in: str,
        check_out: str,
        group_size: int,
        companions: List[Dict[str, Any]] = []
    ) -> dict:
        """Cria uma reserva diretamente pelo painel administrativo.
        Requer: guest_id (obtido via robot_find_guest), room_id, datas e número de hóspedes.
        companions: lista de acompanhantes [{'name': '...', 'age': 0}]."""
        return booking_creation_logic(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions)

    @tool
    def robot_confirm_payment(booking_id: int, method: str = "pix") -> dict:
        """Confirma o pagamento de uma reserva manualmente.
        method: 'pix', 'credito', 'debito', 'dinheiro'.
        Atualiza o status para CONFIRMADO e registra a receita."""
        return confirm_payment_logic(tenant_id, booking_id, method)

    @tool
    def robot_get_payment_info(booking_id: int) -> dict:
        """Obtém os dados de pagamento (QR Code PIX, chave manual) de uma reserva existente."""
        return payment_info_logic(tenant_id, booking_id)

    @tool
    def robot_event_intelligence(search_query: str = "", month: int = None, year: int = None) -> dict:
        """Micro-robô para consultar o CALENDÁRIO DE EVENTOS (Canção Nova, etc).
        Use 'search_query' para buscar pelo nome do evento.
        Use 'month' e 'year' para listar os eventos de determinado período.
        Retorna detalhes como data, descrição e tarifas especiais aplicadas."""
        if search_query:
            return search_events_logic(tenant_id, search_query)
        else:
            return event_listing_logic(tenant_id, month, year)

    tools = [
        robot_booking_summary,
        robot_find_booking,
        robot_find_guest,
        robot_check_availability,
        robot_book_admin,
        robot_confirm_payment,
        robot_get_payment_info,
        robot_event_intelligence,
    ]
    llm_with_tools = llm.bind_tools(tools)

    # ── NÓS DO GRAFO ──────────────────────────────────────────────────────────

    async def call_reservas_admin_model(state: AdminState):
        logger.info(f"[RESERVAS_ADMIN] Processando para tenant {tenant_id}")
        try:
            sys_msg = SystemMessage(content=RESERVAS_ADMIN_SYSTEM_PROMPT)

            # Injeta contexto de reserva se disponível
            context_parts = []
            if state.get("target_booking_id"):
                context_parts.append(f"Reserva em foco: #{state['target_booking_id']}")
            if state.get("target_guest_id"):
                context_parts.append(f"Hóspede em foco ID: {state['target_guest_id']}")
            if state.get("task_context"):
                for k, v in state["task_context"].items():
                    context_parts.append(f"{k}: {v}")

            if context_parts:
                context_sys = SystemMessage(content="📍 CONTEXTO ADMINISTRATIVO:\n" + "\n".join(context_parts))
                messages_to_send = [sys_msg, context_sys] + state["messages"]
            else:
                messages_to_send = [sys_msg] + state["messages"]

            response = await llm_with_tools.ainvoke(messages_to_send)
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"[RESERVAS_ADMIN] Erro crítico: {e}", exc_info=True)
            return {"messages": [AIMessage(content="Tive um problema técnico nas reservas. Pode repetir sua consulta?")]}

    # ── GRAFO ─────────────────────────────────────────────────────────────────

    workflow = StateGraph(AdminState)
    workflow.add_node("reservas_admin_agent", call_reservas_admin_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "reservas_admin_agent")
    workflow.add_conditional_edges("reservas_admin_agent", tools_condition)
    workflow.add_edge("tools", "reservas_admin_agent")

    return workflow.compile()
