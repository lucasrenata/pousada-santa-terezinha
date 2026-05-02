"""
Sub-Agente de Reservas — Especialista em Cotação, Identificação e Criação da Reserva.
"""
import os
import logging
from typing import Dict, Any, List, Optional

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
    RESERVAS_SYSTEM_PROMPT = """Você é a ANA, recepcionista virtual da Pousada.

FUNÇÃO: Conduzir o hóspede até a criação da reserva PENDENTE.

📍 QUADRO DE ATENDIMENTO:
- Verifique SEMPRE o "📍 QUADRO DE ATENDIMENTO" no início da conversa.
- Se os dados (datas, grupo, cpf) estão lá, NÃO PERGUNTE ao hóspede. 
- Use os dados do quadro para chamar as ferramentas (tools) IMEDIATAMENTE.

ESTRATÉGIA PARA GRUPOS GRANDES (MULTI-QUARTOS):
- Se o grupo for maior que a capacidade dos quartos individuais (ex: 6 pessoas), chame `robot_search_available_rooms` para ver todas as opções.
- Sugira ao hóspede uma combinação de quartos (ex: "Vi que vocês são 6 pessoas, temos 3 quartos de casal disponíveis para o período").
- Na hora de criar a reserva, passe a lista de quartos para `robot_create_booking_atomic` separados por vírgula (ex: "101,102,103").

FLUXO OBRIGATÓRIO (NÃO PERGUNTE O QUE JÁ ESTÁ NO QUADRO):
1. COTAR IMEDIATAMENTE: Se você vir Check-in, Check-out e Hóspedes no quadro, chame `robot_calculate_quote` NA HORA.
   - Apresente as opções com o NÚMERO DO QUARTO:
     "🏠 **Quarto [room_id] ([Tipo])** — R$ [total] total (R$ [daily]/diária)"
2. IDENTIFICAR: 
   - Se você não tem o CPF, peça o CPF. Se já tem, chame `robot_identify_guest`.
   - Se o `group_size` > 1 e você ainda não tem os dados de TODOS os acompanhantes (nome e idade), VOCÊ DEVE PERGUNTAR antes de criar a reserva.
   - Pergunte de forma gentil: "Para garantir o valor correto e agilizar seu check-in, poderia me informar o nome e a idade de quem vai com você?"
   - **BOTÃO DE CADASTRO**: Se precisar de registro para o hóspede principal, use Markdown isolado:
     "[📝 Fazer meu Cadastro Agora](URL_DO_LINK)"

3. CRIAR RESERVA: 
   - Condição: Tenho guest_id + room_id(s) + datas + hóspedes + dados dos acompanhantes (se houver).
   - Chame `robot_create_booking_atomic` IMEDIATAMENTE.
   - **PONTE DE PAGAMENTO**: Após criar, confirme os detalhes (Datas e Quartos), comemore e PERGUNTE se ele deseja as instruções para o pagamento do sinal (50% do total) agora.

REGRAS DE OURO:
- Se os dados estão no quadro, considere-os VERDADE ABSOLUTA.
- O objetivo é a reserva #ID o mais rápido possível.
- Resposta SEMPRE em português brasileiro.
"""
    engine = CustomerEngineV2(tenant_id)
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    @tool
    async def robot_calculate_quote(check_in: str, check_out: str, group_size: int = 1) -> dict:
        """Consulta preços e disponibilidade geral para o período e número de pessoas informados."""
        return await engine.robot_calculate_quote(check_in, check_out, group_size)

    @tool
    async def robot_search_available_rooms(check_in: str, check_out: str, group_size: int) -> dict:
        """Busca quartos específicos disponíveis para o grupo nas datas informadas."""
        return await engine.robot_search_available_rooms(check_in, check_out, group_size)

    @tool
    async def robot_identify_guest(cpf: str) -> dict:
        """Identifica o hóspede pelo CPF no banco de dados."""
        return await engine.robot_identify_guest(cpf, session_id)

    @tool
    async def robot_create_booking_atomic(
        guest_id: int,
        room_ids: str,
        check_in: str,
        check_out: str,
        group_size: int,
        companions: Optional[List[Dict[str, Any]]] = None
    ) -> dict:
        """Cria a reserva no banco de dados com status PENDENTE. Aceita um ou mais quartos (separados por vírgula). Inclua a lista de acompanhantes [{'name': '...', 'age': 0}] se houver."""
        return await engine.robot_create_booking_atomic(guest_id, room_ids, check_in, check_out, group_size, companions)

    tools = [robot_calculate_quote, robot_search_available_rooms, robot_identify_guest, robot_create_booking_atomic]
    llm_with_tools = llm.bind_tools(tools)

    def _build_blackboard_msg(state: HotelBookingState) -> SystemMessage:
        blackboard = []
        if state.get("check_in"): blackboard.append(f"Check-in: {state['check_in']}")
        if state.get("check_out"): blackboard.append(f"Check-out: {state['check_out']}")
        if state.get("group_size"): blackboard.append(f"Hóspedes: {state['group_size']}")
        if state.get("cpf"): blackboard.append(f"CPF: {state['cpf']}")
        if state.get("guest_id"): blackboard.append(f"Guest ID: {state['guest_id']}")
        if state.get("room_id"): blackboard.append(f"Quarto Escolhido: {state['room_id']}")
        if state.get("companions"): 
            comp_list = [f"{c['name']} ({c['age']}a)" for c in state['companions']]
            blackboard.append(f"Acompanhantes: {', '.join(comp_list)}")
        
        context_text = "📍 QUADRO DE ATENDIMENTO (DADOS ATUAIS NO BANCO):\n" + ("\n".join(blackboard) if blackboard else "Nenhum dado capturado ainda.")
        return SystemMessage(content=context_text)

    async def call_reservas_model(state: HotelBookingState):
        logger.info(f"[RESERVAS_AGENT] Processando turno para tenant {tenant_id}")
        try:
            custom_persona = await engine.get_ai_persona()
            full_prompt = RESERVAS_SYSTEM_PROMPT
            if custom_persona:
                full_prompt = f"### PERSONALIDADE E TOM DE VOZ (DEFINIDO PELO PROPRIETÁRIO):\n{custom_persona}\n\n" + RESERVAS_SYSTEM_PROMPT
                
            sys_msg = SystemMessage(content=full_prompt)
            context_msg = _build_blackboard_msg(state)
            
            # Chama o modelo com as ferramentas
            response = await llm_with_tools.ainvoke([sys_msg, context_msg] + state["messages"])
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"[RESERVAS_AGENT] Erro crítico na chamada do modelo: {e}")
            return {"messages": [AIMessage(content="Desculpe, tive um problema técnico momentâneo. Pode repetir sua solicitação em alguns segundos?")]}

    workflow = StateGraph(HotelBookingState)
    workflow.add_node("reservas_agent", call_reservas_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "reservas_agent")
    workflow.add_conditional_edges("reservas_agent", tools_condition)
    workflow.add_edge("tools", "reservas_agent")

    return workflow.compile()
