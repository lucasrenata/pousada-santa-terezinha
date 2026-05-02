"""
Sub-Agente de Pagamento — Especialista em Entrega das Instruções de Pagamento.

RESPONSABILIDADE EXCLUSIVA:
  Receber um booking_id JÁ CRIADO (status PENDENTE) e entregar ao hóspede
  a chave PIX real ou o link do Mercado Pago cadastrado na pousada.

  A reserva JÁ FOI CRIADA pelo Agente de Reservas. Este agente apenas
  busca e entrega as instruções de como pagar.

FERRAMENTA:
  - robot_get_payment_info → busca PIX/MP real do TenantConfig

ISOLAMENTO: Não importa nada de admin_agent.py.
"""
import os
import logging

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.session_state import HotelBookingState
from agents.customer_engine import CustomerEngineV2

logger = logging.getLogger("PAGAMENTO_AGENT")


def build_pagamento_graph(tenant_id: int, session_id: str, booking_id: int = None):
    """
    Constrói e retorna o grafo LangGraph do Agente de Pagamento compilado.

    Args:
        booking_id: ID da reserva JÁ CRIADA como PENDENTE pelo Agente de Reservas.
                    Injetado no prompt para evitar que o agente precise "adivinhar".
    """
    engine = CustomerEngineV2(tenant_id)
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # --- FERRAMENTA EXCLUSIVA DE PAGAMENTO ---

    @tool
    async def robot_get_payment_info(booking_id: int) -> dict:
        """Busca as informações de pagamento REAIS cadastradas para esta pousada.
        Retorna a chave PIX manual ou o link do Mercado Pago, dependendo da configuração.
        NUNCA invente dados de pagamento — use SEMPRE este robô."""
        return await engine.robot_get_payment_info(booking_id)

    tools = [robot_get_payment_info]
    llm_with_tools = llm.bind_tools(tools)

    async def call_pagamento_model(state: HotelBookingState):
        current_bid = booking_id or state.get("booking_id")
        logger.info(f"[PAGAMENTO_AGENT] Entregando instruções de pagamento | booking_id={current_bid}")
        
        custom_persona = await engine.get_ai_persona()
        booking_context = f"\n\nCONTEXTO: A reserva #{current_bid} já foi criada com status PENDENTE." if current_bid else ""
        
        base_prompt = f"""Você é a ANA, recepcionista virtual da Pousada.
        
        FUNÇÃO: Entregar as instruções de pagamento para a reserva que acaba de ser criada.{booking_context}
        
        FLUXO OBRIGATÓRIO:
        1. Use `robot_get_payment_info` para obter a chave PIX ou o link de pagamento real.
        2. Apresente as instruções de forma clara:
           - **Se for PIX**: Informe a chave exata e o valor do sinal.
           - **REGRA OBRIGATÓRIA**: Você DEVE solicitar que o hóspede envie o **comprovante do PIX aqui mesmo no chat**. Explique que isso é necessário para que a equipe de hospedagem possa conferir o pagamento e confirmar a reserva definitivamente.
           - **Se for Mercado Pago**: Você DEVE fornecer o link EXATAMENTE como retornado pela ferramenta, sem adicionar espaços. Coloque o link no formato Markdown em uma linha isolada para que o sistema gere um botão:
             [💳 Pagar com Mercado Pago](URL_DO_LINK_SEM_ESPAÇOS)
             
             ⚠️ NUNCA coloque espaços dentro da URL (ex: NUNCA escreva "mercadopago. com. br"). Avise que a confirmação é automática.
        
        REGRAS:
        - Nunca invente dados de pagamento.
        - Se não houver booking_id no quadro ou no histórico, peça ao hóspede o número da reserva.
        - Resposta em Português Brasileiro."""

        full_prompt = base_prompt
        if custom_persona:
            full_prompt = f"### PERSONALIDADE E TOM DE VOZ (DEFINIDO PELO PROPRIETÁRIO):\n{custom_persona}\n\n" + base_prompt
            
        sys_msg = SystemMessage(content=full_prompt)
        
        # --- INJEÇÃO DE CONTEXTO DO BLACKBOARD ---
        blackboard = []
        if current_bid: blackboard.append(f"Booking ID: {current_bid}")
        if state.get("room_id"): blackboard.append(f"Quarto: {state['room_id']}")
        
        context_text = "📍 QUADRO DE ATENDIMENTO (DADOS ATUAIS NO BANCO):\n" + ("\n".join(blackboard) if blackboard else "Nenhum dado capturado ainda.")
        context_msg = SystemMessage(content=context_text)
        
        response = await llm_with_tools.ainvoke([sys_msg, context_msg] + state["messages"])
        return {"messages": [response]}

    workflow = StateGraph(HotelBookingState)
    workflow.add_node("pagamento_agent", call_pagamento_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "pagamento_agent")
    workflow.add_conditional_edges("pagamento_agent", tools_condition)
    workflow.add_edge("tools", "pagamento_agent")

    return workflow.compile()
