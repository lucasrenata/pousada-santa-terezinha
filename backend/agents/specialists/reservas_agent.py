"""
Sub-Agente de Reservas — Especialista em Cotação, Identificação e Criação da Reserva.
"""
import os
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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
    RESERVAS_SYSTEM_PROMPT = """Você é o CONSULTOR DE VENDAS da Pousada Santa Terezinha. Sua missão é seguir o ROTEIRO OFICIAL de 14 passos.

📍 ORDEM DE PRIORIDADE TÉCNICA:
1. **DATAS E PÚBLICO**: Assim que tiver as datas e o número de pessoas (e idades), você DEVE chamar `robot_calculate_quote` e apresentar os valores.
2. **FECHAMENTO DE VALORES**: Confirme se o hóspede aceita o valor e os quartos.
3. **IDENTIFICAÇÃO**: Apenas após o 'OK' do hóspede sobre os valores, peça o CPF.
4. **VERIFICAÇÃO DE CADASTRO**: Chame `robot_identify_guest`. 
   - Se retornar `guest_id`, prossiga para a confirmação final.
   - Se NÃO retornar `guest_id`, informe ao hóspede que ele precisa preencher o cadastro no link que a Ana enviará.
5. **CRIAÇÃO DA RESERVA**: Após o cadastro estar OK (guest_id presente), peça a confirmação final de todos os dados e chame `robot_create_booking_atomic`.

📍 REGRAS DE EXECUÇÃO:
- **PROIBIÇÃO DE CÁLCULOS**: Use apenas os valores dos robôs.
- **NÚMERO DA RESERVA**: Sempre cite o número com # (ex: #123) ao finalizar.
- **PROATIVIDADE**: Se já tem datas e pessoas, não pergunte se quer ver o preço. Dê o preço.
"""
    engine = CustomerEngineV2(tenant_id)
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    @tool
    async def robot_get_booking_details(booking_id: int) -> dict:
        """Busca os detalhes de uma reserva existente pelo ID (número da reserva). 
        Use quando o hóspede quiser saber detalhes de uma reserva que ele já possui."""
        return await engine.robot_get_booking_details(booking_id)

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

    tools = [robot_calculate_quote, robot_search_available_rooms, robot_identify_guest, robot_create_booking_atomic, robot_get_booking_details]
    llm_with_tools = llm.bind_tools(tools)

    def _build_blackboard_msg(state: HotelBookingState) -> SystemMessage:
        from datetime import datetime
        now = datetime.now()
        blackboard = [f"Data Atual: {now.strftime('%d/%m/%Y')}"]
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
            
            # Detecta se é a primeira mensagem do usuário para decidir sobre a saudação
            user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
            is_first_turn = len(user_messages) <= 1
            turn_context = "\n⚠️ CONTEXTO: Início de conversa. Use a saudação de boas-vindas da personalidade." if is_first_turn else "\n⚠️ CONTEXTO: Conversa em andamento. NÃO repita saudações iniciais, seja direto."
            
            full_prompt = RESERVAS_SYSTEM_PROMPT
            if custom_persona:
                full_prompt = f"### PERSONALIDADE E TOM DE VOZ:\n{custom_persona}\n{turn_context}\n\n" + RESERVAS_SYSTEM_PROMPT
                
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
