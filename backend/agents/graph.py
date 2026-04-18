from typing import Dict, Any, List, Annotated, TypedDict
import operator
import logging
from langgraph.graph import StateGraph, END
from datetime import datetime
import json

# Importações dos agentes originais (serão chamados pelos nós)
from agents.fact_extractor import FactExtractorAgent
from agents.specialists.discovery import DiscoverySpecialist
from agents.specialists.validation import ValidationSpecialist
from agents.specialists.confirmation import ConfirmationSpecialist
from agents.specialists.payment import PaymentSpecialist

logger = logging.getLogger(__name__)

def merge_context(old_context: Dict[str, Any], new_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    REDUCER: Realiza a fusão blindada de contextos.
    Garante que dados críticos (check_in, check_out, etc.) não sejam 
    apagados por valores nulos vindos de outros nós.
    """
    if not old_context:
        return new_context or {}
    if not new_context:
        return old_context
    
    merged = old_context.copy()
    for key, val in new_context.items():
        is_valid = val is not None and (val != "" and val != [] and val != {})
        if is_valid:
            merged[key] = val
            
    return merged

class AgentState(TypedDict):
    """
    Estado global do Grafo de Atendimento.
    """
    message: str
    session_id: str
    tenant_id: int
    context: Annotated[Dict[str, Any], merge_context]
    current_state: str
    next_specialist: str
    logic_results: Dict[str, Any]
    response: str
    history: List[Any]

# --- NÓS DO GRAFO ---

async def guardian_node(state: AgentState):
    """Nó do Guardião de Fatos (Extração Pura)"""
    extractor = FactExtractorAgent(state["tenant_id"])
    facts = await extractor.extract(state["message"], state["context"])
    return {"context": facts}

async def logic_node(state: AgentState):
    """Nó de Lógica Determinística (80% Código)"""
    from agents.shared_tools import execute_business_logic
    
    # Processa os fatos extraídos e gera resultados "carimbados" pelo banco
    results = await execute_business_logic(
        tenant_id=state["tenant_id"],
        message=state["message"],
        context=state["context"]
    )
    
    return {"logic_results": results, "context": results.get("updated_context", {})}

async def specialist_node(state: AgentState):
    """Nó de processamento do Especialista Ativo"""
    specialist_name = state["next_specialist"] or "discovery"
    
    # Mapeamento de especialistas
    specialists = {
        "discovery": DiscoverySpecialist,
        "validation": ValidationSpecialist,
        "confirmation": ConfirmationSpecialist,
        "payment": PaymentSpecialist
    }
    
    spec_class = specialists.get(specialist_name, DiscoverySpecialist)
    agent = spec_class(state["tenant_id"])
    
    # IMPORTANTE: No grafo, passamos o contexto do estado e o histórico de mensagens
    result = await agent.process(
        message=state["message"], 
        session_id=state["session_id"], 
        context=state["context"],
        history=state.get("history", []),
        logic_results=state.get("logic_results", {})
    )
    
    return {
        "response": result.get("response", "Desculpe, ocorreu um erro."),
        "current_state": result.get("state", specialist_name),
        "context": result.get("context", {})
    }

# --- DEFINIÇÃO DO WORKFLOW ---

def create_pousada_graph():
    workflow = StateGraph(AgentState)
    
    # Adicionar Nós
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("logic", logic_node)
    workflow.add_node("specialist", specialist_node)
    
    # Definir Fluxo (Sequencial Simples por hora, mas com Guardian enriquecendo o estado)
    workflow.set_entry_point("guardian")
    workflow.add_edge("guardian", "logic")
    workflow.add_edge("logic", "specialist")
    workflow.add_edge("specialist", END)
    
    return workflow.compile()

# Instância global do grafo
pousada_brain = create_pousada_graph()
