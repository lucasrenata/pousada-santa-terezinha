from typing import Dict, Any, List, Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, END
import logging
import json

logger = logging.getLogger(__name__)

def merge_context(old_context: Dict[str, Any], new_context: Dict[str, Any]) -> Dict[str, Any]:
    if not old_context: return new_context or {}
    if not new_context: return old_context
    return {**old_context, **new_context}

class AgentState(TypedDict):
    message: str
    session_id: str
    tenant_id: int
    context: Annotated[Dict[str, Any], merge_context]
    current_state: str
    logic_results: Dict[str, Any]
    response: str
    history: List[Any]

async def guardian_node(state: AgentState):
    """Extração de fatos (V2 isolada)"""
    from agents.fact_extractor import FactExtractorAgent
    extractor = FactExtractorAgent(state["tenant_id"])
    facts = await extractor.extract(state["message"], state["context"])
    return {"context": facts}

async def logic_node(state: AgentState):
    """Orquestrador de Robôs Inteligentes"""
    from agents.customer_engine import CustomerEngineV2
    engine = CustomerEngineV2(state["tenant_id"])
    
    context = state["context"]
    logic_results = {}
    updated_context = {}
    
    # --- ACIONAMENTO DOS ROBÔS (HABILIDADES ATÔMICAS) ---
    
    # 1. Robô de Identidade
    if context.get("cpf") and not context.get("guest_id"):
        logger.info(f"[LOGIC_DEBUG] Acionando Robô de Identidade para CPF: {context['cpf']}")
        res = await engine.robot_identify_guest(context["cpf"], state["session_id"])
        logic_results["guest_robot"] = res
        if res.get("success"):
            logger.info(f"[LOGIC_DEBUG] Hóspede ENCONTRADO: {res['name']}")
            updated_context["guest_id"] = res["guest_id"]
            updated_context["guest_name"] = res["name"]
            updated_context["guest_found"] = True
        else:
            logger.info(f"[LOGIC_DEBUG] Hóspede NÃO encontrado.")
            updated_context["guest_found"] = False
            if res.get("registration_link"):
                updated_context["registration_link"] = res["registration_link"]

    # 2. Robô de Cotação
    if context.get("check_in") and context.get("check_out"):
        logger.info(f"[LOGIC_DEBUG] Acionando Robô de Cotação: {context['check_in']} a {context['check_out']}")
        res = await engine.robot_calculate_quote(context["check_in"], context["check_out"], context.get("group_size", 1))
        logic_results["quote_robot"] = res
        # Persistimos os dados da cotação no contexto para consultas futuras
        if res.get("success"):
            updated_context["last_quote"] = res
            updated_context["available_rooms"] = res.get("rooms", [])

    # 3. Robô de Fechamento (O Script Supremo)
    if all(full_ctx.get(k) for k in ["guest_id", "room_id", "check_in", "check_out"]):
        logger.info(f"[LOGIC_DEBUG] Acionando Robô de Fechamento para Quarto {full_ctx['room_id']}")
        res = await engine.robot_book_and_pay(
            guest_id=full_ctx["guest_id"],
            room_id=full_ctx["room_id"],
            check_in=full_ctx["check_in"],
            check_out=full_ctx["check_out"],
            group_size=full_ctx.get("group_size", 1)
        )
        logic_results["booking_robot"] = res
        if res.get("success"):
            updated_context["booking_done"] = True
            updated_context["payment_details"] = res.get("payment_details", {})
            updated_context["booking_id"] = res.get("booking_details", {}).get("booking_id")
    
    # IMPORTANTE: Se o hóspede já foi encontrado em turnos anteriores, 
    # não podemos regredir para ASK_CPF só porque o FactExtractor não viu o CPF na mensagem atual.
    is_identified = full_ctx.get("guest_found") or full_ctx.get("guest_id")
    
    if not full_ctx.get("cpf") and not is_identified:
        instruction = "Peça o CPF para começar."
        step = "ASK_CPF"
    elif not is_identified:
        instruction = "O hóspede não existe. Entregue o link de cadastro IMEDIATAMENTE."
        step = "GUEST_NOT_FOUND"
    elif not full_ctx.get("check_in") or not full_ctx.get("check_out"):
        instruction = "Peça as datas da reserva."
        step = "ASK_DATES"
    elif not full_ctx.get("room_id"):
        instruction = "Apresente os quartos disponíveis e peça para escolher um."
        step = "SHOW_ROOMS"
    elif not full_ctx.get("booking_done"):
        instruction = "Confirme os detalhes finais e avise que vai gerar a reserva."
        step = "FINAL_CONFIRMATION"
    else:
        instruction = "Reserva criada! Entregue os dados de pagamento (Link e PIX) IMEDIATAMENTE."
        step = "PAYMENT"

    logic_results["engine_instruction"] = instruction
    logic_results["engine_step"] = step

    return {
        "logic_results": logic_results, 
        "context": updated_context,
        "current_state": step
    }

async def responder_node(state: AgentState):
    """Nó único de resposta: Transforma ordens do motor em linguagem natural."""
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import SystemMessage, HumanMessage
    import os

    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    if google_key and gemini_model:
        llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.2)
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.2)

    instruction = state["logic_results"].get("engine_instruction", "Ajude o hóspede.")
    reg_link = state["context"].get("registration_link", "")
    guest_name = state["context"].get("guest_name", "Hóspede")
    guest_found = state["context"].get("guest_found", False)

    prompt = f"""
<SYSTEM_ROLE>
Você é o Orquestrador de Atendimento da Pousada. 
Sua única missão é transformar os DADOS TÉCNICOS do motor em uma resposta calorosa e precisa.
</SYSTEM_ROLE>

<CONTEXTO_ATUAL>
- Hóspede: {guest_name}
- Status: {"Identificado" if guest_found else "Anônimo"}
- Instrução do Motor: {instruction}
- Memória Completa: {json.dumps(state["context"])}
- Resultados da Lógica: {json.dumps(state["logic_results"])}
</CONTEXTO_ATUAL>

<REGRAS_DE_RESPOSTA>
1. USE O NOME: Sempre comece com "Olá {guest_name}" se ele estiver identificado.
2. DADOS REAIS: Só fale o que está em <CONTEXTO_ATUAL>. Se houver quartos em 'quote_robot', LISTE-OS com preços.
3. PAGAMENTO: Se o motor disser "Reserva criada", você DEVE mostrar o Link de Pagamento e o Código PIX (se houver) de forma muito destacada.
4. SEM ALUCINAÇÃO: Nunca diga "estou procurando" ou "um momento". O motor já te deu a resposta final.
5. FORMATO: Use negrito para valores e links. Se houver PIX, peça para copiar e colar.
</REGRAS_DE_RESPOSTA>

<EXEMPLO_QUARTOS>
"Olá Marcos! Encontrei estas opções para você:
- Suíte Master: R$ 500,00
- Quarto Standard: R$ 350,00
Qual deles você prefere?"
</EXEMPLO_QUARTOS>

Responda agora ao hóspede de forma humana, mas estritamente baseada nos dados acima.
"""
    messages = [SystemMessage(content=prompt)]
    if state.get("history"): messages.extend(state["history"])
    messages.append(HumanMessage(content=state["message"]))
    
    response = await llm.ainvoke(messages)
    
    return {"response": response.content}

async def get_pousada_brain():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("logic", logic_node)
    workflow.add_node("responder", responder_node)
    
    workflow.set_entry_point("guardian")
    workflow.add_edge("guardian", "logic")
    workflow.add_edge("logic", "responder")
    workflow.add_edge("responder", END)
    
    return workflow.compile()
