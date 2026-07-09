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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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

    @tool
    async def robot_register_receipt_upload(booking_id: int) -> dict:
        """Registra no sistema que o hóspede enviou um comprovante de pagamento.
        Muda o status para CONFIRMADA e adiciona nota técnica no card da reserva.
        Chame esta ferramenta assim que o hóspede disser que enviou o arquivo ou confirmou o PIX."""
        return await engine.robot_register_receipt_upload(booking_id)

    tools = [robot_get_payment_info, robot_register_receipt_upload]
    llm_with_tools = llm.bind_tools(tools)

    async def call_pagamento_model(state: HotelBookingState):
        current_bid = booking_id or state.get("booking_id")
        logger.info(f"[PAGAMENTO_AGENT] Entregando instruções de pagamento | booking_id={current_bid}")
        
        custom_persona = await engine.get_ai_persona()
        # Detecta se é a primeira mensagem do usuário
        user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        is_first_turn = len(user_messages) <= 1
        turn_context = "\n⚠️ CONTEXTO: Início de conversa. Use a saudação de boas-vindas da personalidade." if is_first_turn else "\n⚠️ CONTEXTO: Conversa em andamento. NÃO repita saudações iniciais, seja direto."
        booking_context = f"\n\nCONTEXTO: A reserva #{current_bid} já foi criada com status PENDENTE." if current_bid else ""
        
        base_prompt = f"""Você é o DIRETOR DE ROTEIRO (PAGAMENTO) da Pousada.
Sua única função é escrever o SCRIPT de pagamento para a reserva #{current_bid}.

📍 RESPOSTA VERBAL OBRIGATÓRIA:
- Após chamar qualquer ferramenta (robot_get_payment_info, robot_register_receipt_upload), você DEVE aguardar o resultado e então escrever uma resposta completa e natural para o hóspede.
- NUNCA termine o seu turno com uma mensagem vazia. Se você recebeu a chave PIX, apresente-a. Se o hóspede enviou o comprovante, confirme o recebimento com entusiasmo.

📍 REGRAS DO TELEPROMPTER:
1. BUSQUE OS DADOS: Use sempre `robot_get_payment_info`.
2. SCRIPT DE PIX (SE AINDA NÃO PAGOU):
   - "Para confirmar, o valor do sinal é R$ [VALOR]. Você pode usar a chave PIX: [CHAVE]. Por favor, envie o comprovante aqui no chat para confirmarmos agora."
3. SCRIPT DE COMPROVANTE RECEBIDO (SE O HÓSPEDE ENVIOU OU DISSE QUE ENVIOU):
   - "Recebido! Já encaminhei seu comprovante para a nossa equipe financeira. Assim que validarmos (o que costuma ser rápido), você receberá a confirmação definitiva por aqui e por e-mail. Posso te ajudar com algo mais?"
4. SCRIPT DE MERCADO PAGO:
   - "Gerei seu link de pagamento seguro. Você pode pagar clicando no botão abaixo. A confirmação é automática."
   - Markdown: `[💳 Pagar com Mercado Pago](URL)`

4. PROIBIDO: Não invente chaves, não peça dados extras, não repita saudações. Seja direto e técnico."""

        full_prompt = base_prompt
        if custom_persona:
            full_prompt = f"### PERSONALIDADE E TOM DE VOZ:\n{custom_persona}\n{turn_context}\n\n" + base_prompt
            
        sys_msg = SystemMessage(content=full_prompt)
        
        # --- INJEÇÃO DE CONTEXTO DO BLACKBOARD ---
        from datetime import datetime
        now = datetime.now()
        blackboard = [f"Data Atual: {now.strftime('%d/%m/%Y')}"]
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
