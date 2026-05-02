"""
Sub-Agente FAQ — Especialista em Dúvidas e Regras da Pousada.

RESPONSABILIDADE EXCLUSIVA: Responder perguntas sobre a pousada (regras, pets,
horários, eventos, políticas). Não toca em reservas, CPF ou pagamentos.

FERRAMENTAS: Somente robot_business_intelligence.
ISOLAMENTO: Não importa nada de admin_agent.py.
"""
import os
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.session_state import HotelBookingState
from agents.customer_engine import CustomerEngineV2

logger = logging.getLogger("FAQ_AGENT")


def build_faq_graph(tenant_id: int, session_id: str):
    """
    Constrói e retorna o grafo LangGraph do Agente FAQ compilado.
    Chamado pelo Supervisor a cada turno.
    """
    engine = CustomerEngineV2(tenant_id)
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # --- FERRAMENTA EXCLUSIVA DO FAQ ---
    @tool
    async def robot_business_intelligence() -> dict:
        """Consulta regras de negócio, manual operacional e calendário de eventos da pousada.
        Use para responder qualquer dúvida sobre: políticas, pets, horários de check-in/out,
        café da manhã, estacionamento, eventos locais e quaisquer regras internas."""
        return await engine.robot_business_intelligence()

    tools = [robot_business_intelligence]
    llm_with_tools = llm.bind_tools(tools)

    async def call_faq_model(state: HotelBookingState):
        logger.info(f"[FAQ_AGENT] Processando turno para tenant {tenant_id}")
        
        custom_persona = await engine.get_ai_persona()
        base_prompt = """Você é a ANA, recepcionista virtual da Pousada, especialista em atendimento e hospitalidade.
        
        FUNÇÃO NESTE TURNO: Responder dúvidas sobre a pousada com simpatia e precisão.
        
        PERSONA:
        - Tom acolhedor, caloroso e profissional.
        - Use frases de hospitalidade: "Com prazer!", "Ótima pergunta!", "Será um prazer esclarecer!"
        
        REGRAS DE OURO:
        1. Use SEMPRE a ferramenta `robot_business_intelligence` antes de responder qualquer dúvida sobre regras ou políticas. NUNCA invente informações.
        2. Se a dúvida for sobre PREÇOS ou RESERVAS, informe que pode verificar disponibilidade e pergunte as datas de interesse.
        3. NUNCA mencione CPF, cadastro ou pagamento neste contexto.
        4. Resposta SEMPRE em português brasileiro."""

        full_prompt = base_prompt
        if custom_persona:
            full_prompt = f"### PERSONALIDADE E TOM DE VOZ (DEFINIDO PELO PROPRIETÁRIO):\n{custom_persona}\n\n" + base_prompt
            
        sys_msg = SystemMessage(content=full_prompt)
        
        # --- INJEÇÃO DE CONTEXTO DO BLACKBOARD ---
        blackboard = []
        if state.get("check_in"): blackboard.append(f"Check-in: {state['check_in']}")
        if state.get("check_out"): blackboard.append(f"Check-out: {state['check_out']}")
        if state.get("group_size"): blackboard.append(f"Hóspedes: {state['group_size']}")
        
        context_text = "📍 QUADRO DE ATENDIMENTO (DADOS ATUAIS NO BANCO):\n" + ("\n".join(blackboard) if blackboard else "Nenhum dado capturado ainda.")
        context_msg = SystemMessage(content=context_text)
        
        response = await llm_with_tools.ainvoke([sys_msg, context_msg] + state["messages"])
        return {"messages": [response]}

    workflow = StateGraph(HotelBookingState)
    workflow.add_node("faq_agent", call_faq_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "faq_agent")
    workflow.add_conditional_edges("faq_agent", tools_condition)
    workflow.add_edge("tools", "faq_agent")

    return workflow.compile()
