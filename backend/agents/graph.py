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
from agents.checkpoint_manager import CheckpointManager

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
            # Lógica especial para listas aditivas (acompanhantes)
            if key == "companions" and isinstance(val, list) and isinstance(merged.get(key), list):
                # Unir listas sem duplicar nomes (baseado no nome)
                existing_names = {c.get("name").lower() for c in merged[key] if c.get("name")}
                for new_c in val:
                    name = new_c.get("name")
                    if name and name.lower() not in existing_names:
                        merged[key].append(new_c)
                        existing_names.add(name.lower())
            else:
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
        context=state["context"],
        session_id=state["session_id"]
    )
    
    updated = results.get("updated_context", {})
    return {"logic_results": results, "context": updated}

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
    
    # IMPORTANTE: mescla o updated_context do logic_node para garantir que os fatos
    # extraidos pelo Guardian e confirmados pela logica cheguem ao especialista
    merged_context = {**state["context"]}
    logic_updated = state.get("logic_results", {}).get("updated_context", {})
    for k, v in logic_updated.items():
        if v is not None and v != "" and v != [] and v != {}:
            merged_context[k] = v
    
    result = await agent.process(
        message=state["message"], 
        session_id=state["session_id"], 
        context=merged_context,
        history=state.get("history", []),
        logic_results=state.get("logic_results", {})
    )
    
    return {
        "response": result.get("response", "Desculpe, ocorreu um erro."),
        "current_state": result.get("state", specialist_name),
        "context": result.get("context", {})
    }

# --- DEFINIÇÃO DO WORKFLOW ---

async def get_pousada_brain():
    """Retorna a instância do cérebro com persistência ativada."""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("logic", logic_node)
    workflow.add_node("specialist", specialist_node)
    
    workflow.set_entry_point("guardian")
    workflow.add_edge("guardian", "logic")
    workflow.add_edge("logic", "specialist")
    workflow.add_edge("specialist", END)
    
    checkpointer = await CheckpointManager.get_instance()
    return workflow.compile(checkpointer=checkpointer)
