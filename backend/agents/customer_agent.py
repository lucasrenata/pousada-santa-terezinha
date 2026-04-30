import json
import os
from sqlalchemy.orm import Session
import models
from database import SessionLocal, set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List, Any
import traceback
from utils.payment_helpers import prepare_payer_data, process_mp_response

from agents import shared_tools
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# =============================================================================
# CONVERSÃO DE HISTÓRICO
# =============================================================================
def convert_history_to_langchain(history: list):
    """Converte o histórico do DB para o formato LangChain."""
    lc_messages = []
    for h in history[-15:]:
        role = h.get("role")
        content = h.get("content", "")
        tool_calls = h.get("tool_calls")
        if role == "user": lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            if tool_calls: lc_messages.append(AIMessage(content=content, tool_calls=tool_calls))
            else: lc_messages.append(AIMessage(content=content))
        elif role == "tool": lc_messages.append(ToolMessage(content=content, tool_call_id=h.get("tool_call_id", "")))
    return lc_messages

# =============================================================================
# ORQUESTRADOR CENTRAL (AGENTE CUSTOMER - A PONTE)
# =============================================================================

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, session_id: str = ""):
    from agents.customer_engine import CustomerEngineV2
    engine = CustomerEngineV2(tenant_id)
    
    # --- SELEÇÃO DE MODELO ---
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)
    
    # --- ATIVAÇÃO DO CONTEXTO ---
    set_tenant_context(db, tenant_id)
    
    # --- BLACKBOARD (Quadro Negro) ---
    from agents.state_manager import StateManager
    sm = StateManager(tenant_id)
    blackboard = sm.get_context(session_id)

    # =========================================================================
    # DEFINIÇÃO DE FERRAMENTAS (OS ROBÔS)
    # =================================================================    @tool
    async def robot_identify_guest(cpf: str) -> dict:
        """Robô 1: Identifica hóspede ou gera link de cadastro. Use sempre que o CPF for fornecido."""
        return await engine.robot_identify_guest(cpf, session_id)

    @tool
    async def robot_calculate_quote(check_in: str, check_out: str, group_size: int = 1) -> dict:
        """Robô 2: Consulta preços e disponibilidade geral. Use na primeira pergunta sobre valores."""
        return await engine.robot_calculate_quote(check_in, check_out, group_size)

    @tool
    async def robot_search_available_rooms(check_in: str, check_out: str, group_size: int) -> dict:
        """Robô 3: Busca quartos específicos que comportam o grupo. Use após o hóspede confirmar interesse na reserva."""
        return await engine.robot_search_available_rooms(check_in, check_out, group_size)

    @tool
    async def robot_create_booking_atomic(guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int) -> dict:
        """Robô 4: Cria a reserva no banco e calcula o valor do sinal. Use apenas após confirmação total dos dados."""
        return await engine.robot_create_booking_atomic(guest_id, room_id, check_in, check_out, group_size)

    @tool
    async def robot_get_payment_info(booking_id: int) -> dict:
        """Robô 5: Gera o link do Mercado Pago ou Chave PIX. Use após a reserva ser criada."""
        return await engine.robot_get_payment_info(booking_id)

    @tool
    async def robot_business_intelligence() -> dict:
        """Robô 7: Consulta Regras de Negócio, Manual e Calendário de Eventos. Use para saber sobre datas especiais, pets, horários e políticas."""
        return await engine.robot_business_intelligence()

    # O Blackboard já foi carregado no início da função
    
    sys_msg = SystemMessage(content=f"""
Você é a ANA, a RECEPCIONISTA VIRTUAL da Pousada. Sua missão é encantar o hóspede com um atendimento caloroso, profissional e eficiente, típico de uma hotelaria de excelência.

PERSONA:
- Seja comunicativa, gentil e use frases de acolhimento (ex: "Será um prazer receber vocês!", "Excelente escolha!", "Deixe-me verificar o melhor para o seu conforto").
- Você NÃO é um robô travado; você é uma profissional de hotelaria que usa ferramentas tecnológicas para garantir dados precisos.

ESTADO ATUAL (QUADRO NEGRO): {json.dumps(blackboard)}

ROTEIRO DE ENCANTAMENTO:
1. CONTEXTO: Use 'robot_business_intelligence' para tirar dúvidas sobre a pousada, pets, horários ou eventos locais. Mostre que você conhece a casa!
2. COTAÇÃO: Use 'robot_calculate_quote' para preços. Ao responder, apresente os valores com entusiasmo e pergunte qual opção mais agrada.
3. IDENTIFICAÇÃO: Se houver interesse, use 'robot_identify_guest'. Peça o CPF com gentileza para localizar o cadastro ou criar um novo.
4. ESCOLHA: Use 'robot_search_available_rooms' para mostrar as fotos e detalhes dos quartos.
5. FINALIZAÇÃO: Use 'robot_create_booking_atomic' para selar a reserva e 'robot_get_payment_info' para facilitar o pagamento.

REGRAS DE OURO:
- NUNCA diga que vai "esperar" ou "localizar". Use o robô IMEDIATAMENTE e responda já com o resultado.
- NUNCA envie links por extenso (URLs). Sempre use o formato de botão Markdown em uma nova linha: [Texto do Botão](URL).
- Se o hóspede não tiver cadastro, entregue o botão de cadastro IMEDIATAMENTE após a Ana se apresentar.
- Mantenha o foco em converter a conversa em uma reserva feliz!
""")

    tools = [
        robot_identify_guest, 
        robot_calculate_quote, 
        robot_search_available_rooms, 
        robot_create_booking_atomic,
        robot_get_payment_info,
        robot_business_intelligence
    ]
    
    # --- CONSTRUÇÃO DO GRAFO (AGENTE REATIVO) ---
    def call_model(state: MessagesState):
        return llm.bind_tools(tools).invoke([sys_msg] + state["messages"])

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    
    app = workflow.compile()
    
    try:
        # Registramos quantas mensagens tínhamos antes para pegar apenas as NOVAS
        initial_msg_count = len(history) + 1 # +1 pela HumanMessage que vamos enviar
        
        final_state = await app.ainvoke({"messages": convert_history_to_langchain(history) + [HumanMessage(content=message)]})
        
        # --- COLETA DE TODAS AS RESPOSTAS DA IA NESTE TURNO ---
        # Queremos todas as AIMessages que surgiram após a nossa HumanMessage
        new_messages = final_state["messages"][initial_msg_count:]
        ai_responses = [m.content for m in new_messages if isinstance(m, AIMessage) and m.content]
        
        response_content = " ".join(ai_responses).strip()
        
        # --- NORMALIZAÇÃO ROBUSTA ---
        if isinstance(response_content, list):
            response_content = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in response_content]).strip()
        
        # --- VÁLVULA DE ESCAPE INTELIGENTE ---
        if not response_content or response_content.strip() == "":
            print(f"[AI_DEBUG] IA silenciou. Recuperando dados dos robôs...")
            for m in reversed(final_state["messages"]):
                if isinstance(m, ToolMessage):
                    try:
                        res = json.loads(m.content)
                        # Se foi cotação
                        if "total" in res and "breakdown" in res:
                            response_content = f"Para esse período, o valor total fica em R$ {res['total']:.2f}. Qual desses quartos você prefere reservar?"
                            break
                        # Se foi identificação
                        if res.get("registration_link"):
                            response_content = f"Notei que você ainda não tem cadastro conosco. Será um prazer te receber! Para continuarmos, basta clicar no botão abaixo:\n\n[💎 Clique aqui para se Cadastrar]({res['registration_link']})"
                            break
                    except: continue
            
            if not response_content:
                response_content = "Entendido! Como posso te ajudar a prosseguir com o seu atendimento?"

        return {"response": response_content}
    except Exception as e:
        traceback.print_exc()
        return {"response": f"Erro técnico na ponte: {str(e)}"}
