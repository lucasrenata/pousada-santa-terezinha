"""
Sub-Agente de Reservas — Especialista em Cotação, Identificação e Criação da Reserva.

RESPONSABILIDADE EXCLUSIVA:
  1. Coletar datas e número de pessoas.
  2. Apresentar opções de quartos do mais barato ao mais caro.
  3. Identificar o hóspede pelo CPF (ou gerar link de cadastro).
  4. Coletar dados dos acompanhantes (nome e idade).
  5. Criar a reserva como PENDENTE no banco → gera o booking_id.

FERRAMENTAS:
  - robot_calculate_quote        → cotação inicial (ordena por preço)
  - robot_search_available_rooms → quartos disponíveis para o grupo
  - robot_identify_guest         → busca CPF ou gera link de cadastro
  - robot_create_booking_atomic  → CRIA a reserva como PENDENTE

ISOLAMENTO: Não importa nada de admin_agent.py.
"""
import os
import logging
from typing import Dict, Any

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.session_state import HotelBookingState
from agents.customer_engine import CustomerEngineV2

logger = logging.getLogger("RESERVAS_AGENT")


def build_reservas_graph(tenant_id: int, session_id: str):
    """
    Constrói e retorna o grafo LangGraph do Agente de Reservas compilado.
    """
    engine = CustomerEngineV2(tenant_id)
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # --- FERRAMENTAS EXCLUSIVAS DE RESERVAS ---

    @tool
    async def robot_calculate_quote(check_in: str, check_out: str, group_size: int = 1) -> dict:
        """Consulta preços e disponibilidade geral para o período e número de pessoas informados.
        Retorna opções ordenadas do mais barato ao mais caro.
        Formatos de data aceitos: DD/MM/YYYY, DD/MM ou YYYY-MM-DD."""
        return await engine.robot_calculate_quote(check_in, check_out, group_size)

    @tool
    async def robot_search_available_rooms(check_in: str, check_out: str, group_size: int) -> dict:
        """Busca quartos específicos disponíveis para o grupo nas datas informadas.
        Use para confirmar disponibilidade de uma categoria específica escolhida pelo hóspede."""
        return await engine.robot_search_available_rooms(check_in, check_out, group_size)

    @tool
    async def robot_identify_guest(cpf: str) -> dict:
        """Identifica o hóspede pelo CPF no banco de dados.
        Se não encontrado, retorna um link de cadastro para o hóspede se registrar.
        Use SEMPRE que o hóspede informar o CPF."""
        return await engine.robot_identify_guest(cpf, session_id)

    @tool
    async def robot_create_booking_atomic(
        guest_id: int,
        room_id: str,
        check_in: str,
        check_out: str,
        group_size: int
    ) -> dict:
        """Cria a reserva no banco de dados com status PENDENTE, de forma atômica e segura.
        Use SOMENTE após ter TODOS os dados confirmados:
          - guest_id: ID do hóspede (retornado por robot_identify_guest)
          - room_id: número do quarto escolhido pelo hóspede
          - check_in / check_out: datas no formato DD/MM/YYYY
          - group_size: número total de hóspedes (incluindo o titular)
        Retorna booking_id, total_amount e down_payment (valor do sinal a pagar)."""
        return await engine.robot_create_booking_atomic(guest_id, room_id, check_in, check_out, group_size)

    tools = [robot_calculate_quote, robot_search_available_rooms, robot_identify_guest, robot_create_booking_atomic]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content="""Você é a ANA, recepcionista virtual da Pousada.

FUNÇÃO: Conduzir o hóspede até a criação da reserva PENDENTE.

DIRETRIZ DO QUADRO DE ATENDIMENTO:
- Verifique SEMPRE o "📍 QUADRO DE ATENDIMENTO" no início da conversa.
- Se os dados (datas, grupo, cpf) estão lá, NÃO PERGUNTE ao hóspede. 
- Use os dados do quadro para chamar as ferramentas (tools) IMEDIATAMENTE.

FLUXO OBRIGATÓRIO (NÃO PERGUNTE O QUE JÁ ESTÁ NO QUADRO):
1. COTAR IMEDIATAMENTE: Se você vir Check-in, Check-out e Hóspedes no quadro, chame `robot_calculate_quote` NA HORA. Não peça permissão, não dê "Olá" de novo, apenas traga os preços.
   - Apresente as opções com o NÚMERO DO QUARTO:
     "🏠 **Quarto [room_id] ([Tipo])** — R$ [total] total (R$ [daily]/diária)"
2. IDENTIFICAR: Se o hóspede já escolheu um quarto mas você ainda não tem o CPF no quadro, peça o CPF. Se já tem o CPF no quadro, chame `robot_identify_guest`.
3. CRIAR RESERVA: Se você tem guest_id + room_id + datas + hóspedes, chame `robot_create_booking_atomic` SEM HESITAR. 

REGRAS DE OURO:
- Se os dados estão no 📍 QUADRO DE ATENDIMENTO, considere-os como VERDADE ABSOLUTA.
- O seu objetivo é chegar na reserva #ID o mais rápido possível.
- Use links Markdown: `[Texto](URL)`.
- Resposta SEMPRE em português brasileiro.
""")

    def call_reservas_model(state: HotelBookingState):
        logger.info(f"[RESERVAS_AGENT] Processando turno para tenant {tenant_id}")
        
        # --- INJEÇÃO DE CONTEXTO DO BLACKBOARD ---
        blackboard = []
        if state.get("check_in"): blackboard.append(f"Check-in: {state['check_in']}")
        if state.get("check_out"): blackboard.append(f"Check-out: {state['check_out']}")
        if state.get("group_size"): blackboard.append(f"Hóspedes: {state['group_size']}")
        if state.get("cpf"): blackboard.append(f"CPF: {state['cpf']}")
        if state.get("guest_id"): blackboard.append(f"Guest ID: {state['guest_id']}")
        if state.get("room_id"): blackboard.append(f"Quarto Escolhido: {state['room_id']}")
        
        context_text = "📍 QUADRO DE ATENDIMENTO (DADOS ATUAIS NO BANCO):\n" + ("\n".join(blackboard) if blackboard else "Nenhum dado capturado ainda.")
        
        # Adiciona o contexto como uma mensagem de sistema temporária para orientar o modelo
        context_msg = SystemMessage(content=context_text)
        
        response = llm_with_tools.invoke([sys_msg, context_msg] + state["messages"])
        return {"messages": [response]}

    workflow = StateGraph(HotelBookingState)
    workflow.add_node("reservas_agent", call_reservas_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "reservas_agent")
    workflow.add_conditional_edges("reservas_agent", tools_condition)
    workflow.add_edge("tools", "reservas_agent")

    return workflow.compile()
