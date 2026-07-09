"""
AgenteOperacoes — Especialista em Operações de Quarto e Hospedagem Ativa.
Responsabilidade: Tudo relacionado a quartos que estão sendo usados AGORA.
Domínio: status de quartos, lançamento de consumo, detalhes de ocupação, checkout.
SEPARADO TOTALMENTE DO AGENTE CUSTOMER.
"""
import os
import logging
from typing import List, Optional

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.admin_state import AdminState

logger = logging.getLogger("ADMIN.OPERACOES")

OPERACOES_SYSTEM_PROMPT = """Você é o AGENTE DE OPERAÇÕES da pousada — o especialista em tudo que acontece nos quartos agora.

## SUA FUNÇÃO
Gerenciar o estado operacional do hotel em tempo real: status de quartos, consumos, extratos e checkouts.

## SUAS FERRAMENTAS (use com precisão)
- `robot_room_viewer`: Ver lista e status de todos os quartos (filtre por status se pedido)
- `robot_room_status_manager`: Mudar status de um quarto (limpeza, manutenção, disponível)
- `robot_mark_room_as_ready`: Atalho rápido para liberar um quarto limpo
- `robot_room_occupancy_details`: Extrato completo de um quarto ocupado (consumos, hóspede, saldo)
- `robot_consumption_launcher`: Lançar item de consumo (bebida, serviço, etc) na conta de um quarto
- `robot_checkout_manager`: Prévia ou confirmação de checkout de um quarto

## REGRAS DE OURO
1. **Ação antes de pergunta**: Se você tem o quarto e o item, execute sem pedir confirmação dupla.
2. **Sempre confirme**: Após executar qualquer ação, confirme claramente o resultado ("Feito! 2 refrigerantes lançados no quarto 101").
3. **Extrato antes de checkout**: Se o usuário pedir checkout, sempre faça a prévia primeiro (action=preview) e mostre o total antes de confirmar.
4. **Tom direto e operacional**: Seja rápido e preciso como um gerente de andar.

## EXEMPLOS DE COMANDOS
- "Adiciona 2 cervejas no quarto 101" → robot_consumption_launcher(room_id="101", product_name="cerveja", quantity=2)
- "Quarto 205 está pronto" → robot_mark_room_as_ready(room_id="205")
- "Quantos quartos estão em limpeza?" → robot_room_viewer(status="limpeza")
- "Quanto o hóspede do 303 deve?" → robot_room_occupancy_details(room_id="303")
- "Fecha a conta do 101 no cartão" → robot_checkout_manager(room_id="101", confirm=False) primeiro, depois confirm=True

Responda sempre em português brasileiro. Seja direto e resolutivo.
"""


def build_operacoes_graph(tenant_id: int):
    """
    Constrói e retorna o grafo LangGraph do Agente de Operações compilado.
    """
    from agents.admin_agent import (
        room_viewer_logic,
        room_status_logic,
        consumption_logic,
        checkout_logic,
        room_occupancy_details_logic,
    )

    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # ── FERRAMENTAS RESTRITAS DO ESPECIALISTA ──────────────────────────────────

    @tool
    def robot_room_viewer(status: Optional[str] = None) -> dict:
        """Lista e conta quartos por status. status pode ser: 'disponivel', 'limpeza', 'manutencao', 'ocupado' ou None para todos."""
        return room_viewer_logic(tenant_id, status)

    @tool
    def robot_room_status_manager(room_id: str, new_status: str, note: str = "") -> dict:
        """Altera o status de um quarto. new_status: 'disponivel', 'limpeza' ou 'manutencao'."""
        return room_status_logic(tenant_id, room_id, new_status, note)

    @tool
    def robot_mark_room_as_ready(room_id: str) -> dict:
        """Atalho para liberar um quarto: marca como limpo e disponível imediatamente."""
        return room_status_logic(tenant_id, room_id, "disponivel")

    @tool
    def robot_room_occupancy_details(room_id: str) -> dict:
        """Retorna extrato completo de um quarto com check-in ativo: hóspede, consumos, saldo parcial e datas."""
        return room_occupancy_details_logic(tenant_id, room_id)

    @tool
    def robot_consumption_launcher(room_id: str, product_name: str, quantity: int = 1) -> dict:
        """Lança itens de consumo (bebidas, serviços, etc) na conta de um quarto com check-in ativo.
        Deduz automaticamente do estoque."""
        return consumption_logic(tenant_id, room_id, product_name, quantity)

    @tool
    def robot_checkout_manager(room_id: str, confirm: bool = False, payment_method: str = "pix") -> dict:
        """Gerencia checkout de um quarto.
        confirm=False: prévia do total a pagar.
        confirm=True: fecha a conta e libera o quarto para limpeza.
        payment_method: 'pix', 'credito', 'debito', 'dinheiro'."""
        action = "confirm" if confirm else "preview"
        return checkout_logic(tenant_id, room_id, action, payment_method)

    tools = [
        robot_room_viewer,
        robot_room_status_manager,
        robot_mark_room_as_ready,
        robot_room_occupancy_details,
        robot_consumption_launcher,
        robot_checkout_manager,
    ]
    llm_with_tools = llm.bind_tools(tools)

    # ── NÓS DO GRAFO ──────────────────────────────────────────────────────────

    async def call_operacoes_model(state: AdminState):
        logger.info(f"[OPERACOES] Processando para tenant {tenant_id}")
        try:
            sys_msg = SystemMessage(content=OPERACOES_SYSTEM_PROMPT)

            # Injeta contexto operacional no prompt se disponível
            context_parts = []
            if state.get("target_room_id"):
                context_parts.append(f"Quarto em foco: {state['target_room_id']}")
            if state.get("task_context"):
                for k, v in state["task_context"].items():
                    context_parts.append(f"{k}: {v}")

            if context_parts:
                context_sys = SystemMessage(content="📍 CONTEXTO OPERACIONAL:\n" + "\n".join(context_parts))
                messages_to_send = [sys_msg, context_sys] + state["messages"]
            else:
                messages_to_send = [sys_msg] + state["messages"]

            response = await llm_with_tools.ainvoke(messages_to_send)
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"[OPERACOES] Erro crítico: {e}", exc_info=True)
            return {"messages": [AIMessage(content="Tive um problema técnico momentâneo nas operações. Pode repetir?")]}

    # ── GRAFO ─────────────────────────────────────────────────────────────────

    workflow = StateGraph(AdminState)
    workflow.add_node("operacoes_agent", call_operacoes_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "operacoes_agent")
    workflow.add_conditional_edges("operacoes_agent", tools_condition)
    workflow.add_edge("tools", "operacoes_agent")

    return workflow.compile()
