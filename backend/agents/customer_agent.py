import json
import os
from sqlalchemy.orm import Session
import models
from database import SessionLocal, set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List
import traceback
from utils.payment_helpers import prepare_payer_data, process_mp_response

from agents import shared_tools
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
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
# ORQUESTRADOR CENTRAL (AGENTE CUSTOMER)
# =============================================================================

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, base_url: str = ""):
    # --- SELEÇÃO DE MODELO (OPENAI VS GEMINI) ---
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    
    if google_key:
        model_name = gemini_model or "gemini-2.5-flash-lite-preview"
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=google_key, temperature=0.1)
        print(f"[AI_LOG] Ativando Modelo Experimental: {model_name}")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.2)
        print(f"[AI_LOG] Usando OpenAI: gpt-4o-mini")

    # --- BUSCA NOME DA IA E CONFIGURAÇÕES ---
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
    ai_name = settings.get("ai_receptionist_name", "Ana")

    @tool
    def robot_check_availability(check_in: str, check_out: str, group_size: int = 1, ages: List[int] = []) -> dict:
        """Micro-robô para consultar vagas e preços. Use sempre que o hóspede perguntar datas, valores ou disponibilidade."""
        return shared_tools.availability_check_logic(tenant_id, check_in, check_out, group_size, ages)

    @tool
    def robot_find_guest(cpf: str = "", name: str = "") -> dict:
        """Micro-robô para identificar hóspedes no banco de dados."""
        return shared_tools.find_guest_logic(tenant_id, cpf, name, base_url)

    @tool
    def robot_pre_validate_checklist(group_size: int, companions: List[dict] = []) -> dict:
        """Micro-robô de validação: Verifique se os dados de todos os acompanhantes foram coletados."""
        # Nota: pre_validation_logic foi movido para o shared_tools mas não foi exportado no script anterior
        # Vou usar a lógica direta aqui por enquanto para não quebrar.
        missing = []
        total_expected = group_size - 1
        if len(companions) < total_expected: missing.append(f"Mais {total_expected - len(companions)} acompanhantes")
        return {"status": "ready" if not missing else "incomplete", "missing": missing}

    @tool
    def robot_search_events(query: str) -> dict:
        """Micro-robô de consulta de eventos locais."""
        # Lógica simplificada ou importada se disponível
        return {"results": []}

    @tool
    def robot_book_with_payment(guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = []) -> dict:
        """Micro-robô FINALIZADOR: Realiza a reserva e gera a cobrança PIX."""
        return shared_tools.unified_booking_flow(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions)

    @tool
    def robot_confirm_payment(booking_id: int, method: str = "pix") -> dict:
        """Micro-robô financeiro: Confirma pagamentos e libera a reserva."""
        return shared_tools.confirm_payment_logic(tenant_id, booking_id, method)

    @tool
    def robot_get_payment_info(booking_id: int) -> dict:
        """Micro-robô de COBRANÇA: Gera ou recupera o QR Code PIX e dados de pagamento para uma reserva existente."""
        return shared_tools.payment_info_logic(tenant_id, booking_id)

    @tool
    def robot_find_booking(cpf: str = "", name: str = "", room_id: str = "", booking_id: int = None) -> dict:
        """Micro-robô de INVESTIGAÇÃO: Localiza detalhes de uma reserva pelo ID, CPF, Nome ou Quarto. Use para validar IDs."""
        return shared_tools.find_booking_logic(tenant_id, cpf, name, room_id, booking_id)

    @tool
    def robot_record_knowledge(content: str, category: str = "geral", importance: int = 1, guest_id: int = None) -> dict:
        """Micro-robô de Memória: Salva fatos ou preferências aprendidas para uso futuro."""
        return shared_tools.store_operational_memory_logic(tenant_id, content, category, guest_id, importance)

    # --- MEMÓRIA E DIAGNÓSTICO ---
    # Tenta identificar o hóspede no histórico para carregar a memória específica
    current_guest_id = None
    for h in reversed(history):
        if h.get("guest_id"): 
            current_guest_id = h["guest_id"]
            break
            
    op_memory = shared_tools.get_operational_memory_logic(tenant_id, current_guest_id)
    if op_memory: print(f"[AI_MEMORY] Carregados fatos da memória operacional.")

    # --- PERSONA TRANSAIONAL (PROMPT SÊNIOR) ---
    current_date_str = date.today().strftime("%A, %d de %B de %Y")
    sys_msg = SystemMessage(content=f"""Hoje é {current_date_str}.
Você é {ai_name}, o Orquestrador de Recepção Virtual. Sua prioridade é PRECISÃO TRANSAIONAL.
{op_memory}

REGRAS OBRIGATÓRIAS DE ORQUESTRAÇÃO:

1. VALIDAÇÃO ANTES DA RESERVA:
   - Você é PROIBIDO de chamar 'robot_book_with_payment' se o 'robot_pre_validate_checklist' retornar 'incomplete'.
   - Se faltar dados, peça-os de forma clara e objetiva.

2. PROTOCOLO DE CONFIRMAÇÃO:
   - Antes de efetivar a reserva, você DEVE apresentar um resumo detalhado:
     * Check-in e Check-out
     * Quarto selecionado (Número/Tipo)
     * Pessoas (Titular + Acompanhantes)
     * Valor Total
   - Pergunte explicitamente: "As informações acima estão corretas? Podemos seguir para o pagamento?"
   - SÓ execute a reserva após o hóspede dizer "Sim", "Pode", "Está correto" ou similar.

3. TRATAMENTO DE IDADES:
   - Se o hóspede não informar a idade de um acompanhante, assuma 18 anos APENAS se ele confirmar (ex: "São todos adultos?"). Caso contrário, pergunte a idade.

4. PRECISÃO DE DADOS (ZERO ALUCINAÇÃO):
   - Nunca invente guest_id, room_id ou valores. Use APENAS o que os robôs retornarem.
   - Trate erros de robôs de forma transparente: se um robô falhar (ex: 'Idade inválida'), explique ao hóspede o que falhou e peça a correção.

6. REGRAS DE PRODUÇÃO E VERDADE FINANCEIRA:
   - VOCÊ NUNCA DEVE CONFIRMAR UM PAGAMENTO OU RESERVA SEM RETORNO DE SUCESSO DE UMA FERRAMENTA.
   - Se o hóspede enviar um comprovante, responda APENAS: "Obrigado! Recebi seu arquivo. Vou encaminhar para nossa equipe validar e sua reserva será confirmada em breve."
   - É PROIBIDO dizer "Pagamento processado", "Reserva confirmada" ou "Tudo certo" apenas porque o usuário enviou um anexo. Você não tem visão real do arquivo, por isso deve ser cauteloso.
   - Nunca invente ou alucine IDs de reserva. Se o robô não retornou o ID, não o mencione.
   - Nunca gere um QR Code se o hóspede não forneceu o CPF. O sistema de produção do Mercado Pago recusa CPFs em branco ou falsos.
   - Sempre valide com o hóspede se os dados de contato estão corretos antes de chamar a ferramenta de pagamento.
   - Se o hóspede pedir para pagar uma reserva que já existe, use obrigatoriamente o 'robot_get_payment_info'.
   - VOCÊ NUNCA DEVE DIZER QUE NÃO CONSEGUE GERAR PAGAMENTO. Se tiver o booking_id, use a ferramenta de cobrança.
   - SEMPRE forneça o link clicável de pagamento ('payment_url') se disponível. Instrua o hóspede a clicar no link caso tenha dificuldade com o QR Code.
   - APRESENTE O CÓDIGO PIX (Copia e Cola) de forma clara e isolada para facilitar a cópia no celular.

7. PROTOCOLO DE ID DA RESERVA (REGRA DE OURO):
   - O ID da reserva (ex: #123) é SOBERANO e SUFICIENTE.
   - Se o hóspede fornecer o ID, você DEVE realizar a consulta ou gerar o pagamento IMEDIATAMENTE.
   - É terminantemente PROIBIDO pedir CPF ou Nome se você já tem o ID da reserva.
   - Se o hóspede pedir para pagar uma reserva e der o ID, use 'robot_get_payment_info' na hora.
   - Use 'robot_find_booking' para validar IDs ou buscar reservas se o hóspede apenas der o CPF/Nome.

ESTILO: Profissional, eficiente e acolhedor, mas focado na conclusão correta da transação.
""")

    tools = [
        robot_check_availability, robot_find_guest, robot_search_events, 
        robot_pre_validate_checklist, robot_book_with_payment, robot_confirm_payment,
        robot_record_knowledge, robot_get_payment_info, robot_find_booking
    ]
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: MessagesState):
        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", lambda s: "tools" if s["messages"][-1].tool_calls else END)
    workflow.add_edge("tools", "agent")
    app = workflow.compile()

    # Conversão Inteligente de Histórico
    lc_messages = convert_history_to_langchain(history)
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        response_msg = final_state["messages"][-1]
        response_content = response_msg.content
        
        # --- NORMALIZAÇÃO NATIVA (THE GEMINI WAY) ---
        # Extrai o texto de blocos complexos ou serializa para String para o banco
        if isinstance(response_content, list):
            full_text = ""
            for part in response_content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        full_text += part.get("text", "")
                elif isinstance(part, str):
                    full_text += part
            response_content = full_text.strip()
        
        # Se for um AIMessage com chamadas de ferramenta mas sem texto, o Gemini às vezes retorna vazio
        if not response_content and hasattr(response_msg, 'tool_calls') and response_msg.tool_calls:
            response_content = "Processando informações com meus robôs... 🤖"

        return {"response": response_content}
    except Exception as e:
        import traceback
        # --- LOG DE DIAGNÓSTICO SÊNIOR (ERROR 404 DETECT) ---
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            print(f"\n[AI_DIAGNOSTIC_ERROR] Erro 404 Detectado ao chamar o modelo {gemini_model or 'gemini-2.0-flash-001'}")
            print(f"Detalhes Técnicos: {error_msg}")
            # Tenta extrair informações extras se vierem do Google GenAI
            if hasattr(e, 'response'):
                try:
                    print(f"Resposta Bruta da API: {e.response.json if hasattr(e.response, 'json') else e.response}")
                except: pass
        
        traceback.print_exc()
        return {"response": f"Ops! Tive um pequeno tropeço técnico aqui: {str(e)}. Mas já estou me levantando, pode tentar de novo?"}
