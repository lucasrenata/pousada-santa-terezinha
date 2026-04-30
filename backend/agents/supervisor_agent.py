"""
SupervisorAgent — Orquestrador Hierárquico do Atendimento ao Hóspede (FSM Edition).
"""
import logging
import re
import json
import os
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

import models
from database import SessionLocal, set_tenant_context
from agents.schemas.session_state import HotelBookingState

logger = logging.getLogger("SUPERVISOR")

def extract_state_from_history(messages: list) -> Dict[str, Any]:
    from utils.date_parser import extract_dates_from_text, extract_group_size_from_text
    state_update = {}
    # Captura apenas mensagens humanas para extração de desejos do hóspede
    full_text = " ".join([m.content for m in messages if isinstance(m, HumanMessage) and isinstance(m.content, str)])
    
    logger.debug(f"[EXTRACTOR] Texto para análise: {full_text}")
    
    check_in, check_out = extract_dates_from_text(full_text)
    if check_in: state_update["check_in"] = check_in
    if check_out: state_update["check_out"] = check_out
    
    group_size = extract_group_size_from_text(full_text)
    if group_size: state_update["group_size"] = group_size
    
    cpf_match = re.search(r'\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b', full_text)
    if cpf_match: state_update["cpf"] = re.sub(r'\D', '', cpf_match.group(1))

    # Detecção de room_id (ex: "quarto 102", "quarto número 101", "número 303")
    room_match = re.search(r'\b(?:quarto|número|room|nº|#)\s*[:#]?\s*(\d{3})\b', full_text, re.IGNORECASE)
    if room_match: state_update["room_id"] = room_match.group(1)
    
    return state_update

class SupervisorAgent:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def _get_workflow(self, checkpointer=None):
        workflow = StateGraph(HotelBookingState)
        workflow.add_node("sync_blackboard", self.sync_blackboard_node)
        workflow.add_node("gatekeeper_extractor", self.extractor_node)
        workflow.add_node("reservas_agent", self.reservas_node)
        workflow.add_node("pagamento_agent", self.pagamento_node)
        workflow.add_node("faq_agent", self.faq_node)

        workflow.add_edge(START, "sync_blackboard")
        workflow.add_edge("sync_blackboard", "gatekeeper_extractor")
        workflow.add_conditional_edges("gatekeeper_extractor", self.fsm_router, {"reservas": "reservas_agent", "pagamento": "pagamento_agent", "faq": "faq_agent"})
        workflow.add_edge("reservas_agent", END)
        workflow.add_edge("pagamento_agent", END)
        workflow.add_edge("faq_agent", END)
        
        return workflow.compile(checkpointer=checkpointer)

    async def sync_blackboard_node(self, state: HotelBookingState):
        from agents.state_manager import StateManager
        sm = StateManager(self.tenant_id)
        persisted = sm.get_context(state["session_id"])
        logger.info(f"[FSM][SYNC] Dados do banco: {persisted}")
        return {
            "check_in": persisted.get("check_in"),
            "check_out": persisted.get("check_out"),
            "group_size": persisted.get("group_size", 1),
            "room_id": persisted.get("room_id"),
            "guest_id": persisted.get("guest_id"),
            "booking_id": persisted.get("booking_id"),
            "cpf": persisted.get("cpf"),
        }

    async def extractor_node(self, state: HotelBookingState):
        # O extractor olha todo o histórico atual para não perder nada
        extracted = extract_state_from_history(state["messages"])
        logger.info(f"[FSM][EXTRACTOR] Novas entidades: {extracted}")
        return extracted

    def fsm_router(self, state: HotelBookingState) -> str:
        last_msg = state["messages"][-1].content.lower()
        if any(kw in last_msg for kw in ["pet", "animal", "horário", "piscina"]): return "faq"
        if state.get("booking_id"): return "pagamento"
        return "reservas"

    async def reservas_node(self, state: HotelBookingState):
        from agents.specialists.reservas_agent import build_reservas_graph
        graph = build_reservas_graph(self.tenant_id, state["session_id"])
        
        # Prepara entrada: Blackboard no topo + histórico
        board_msg = self._build_blackboard_msg(state)
        input_messages = [board_msg] + state["messages"]
        
        logger.info(f"[FSM][RESERVAS] Iniciando sub-grafo...")
        res = await graph.ainvoke({"messages": input_messages})
        
        # Retorna apenas as mensagens que o especialista ADICIONOU (ignorando o input)
        new_count = len(res["messages"]) - len(input_messages)
        return {"messages": res["messages"][-new_count:] if new_count > 0 else []}

    async def pagamento_node(self, state: HotelBookingState):
        from agents.specialists.pagamento_agent import build_pagamento_graph
        graph = build_pagamento_graph(self.tenant_id, state["session_id"], booking_id=state.get("booking_id"))
        
        board_msg = self._build_blackboard_msg(state)
        input_messages = [board_msg] + state["messages"]
        
        logger.info(f"[FSM][PAGAMENTO] Iniciando sub-grafo...")
        res = await graph.ainvoke({"messages": input_messages})
        
        new_count = len(res["messages"]) - len(input_messages)
        return {"messages": res["messages"][-new_count:] if new_count > 0 else []}

    async def faq_node(self, state: HotelBookingState):
        from agents.specialists.faq_agent import build_faq_graph
        graph = build_faq_graph(self.tenant_id, state["session_id"])
        
        input_messages = state["messages"]
        res = await graph.ainvoke({"messages": input_messages})
        
        new_count = len(res["messages"]) - len(input_messages)
        return {"messages": res["messages"][-new_count:] if new_count > 0 else []}

    def _build_blackboard_msg(self, state: HotelBookingState) -> SystemMessage:
        b = []
        if state.get("check_in"): b.append(f"- PERÍODO: {state['check_in']} a {state['check_out']}")
        if state.get("room_id"): b.append(f"- QUARTO: {state['room_id']}")
        if state.get("guest_id"): b.append(f"- HÓSPEDE ID: {state['guest_id']}")
        if state.get("cpf") and not state.get("guest_id"): b.append(f"- CPF: {state['cpf']}")
        if state.get("booking_id"): b.append(f"- RESERVA: #{state['booking_id']}")
        return SystemMessage(content="📍 QUADRO DE ATENDIMENTO:\n" + ("\n".join(b) if b else "(Vazio)") + "\n\nAVISO: Use estes fatos. Se o período está lá, não pergunte.")

    async def process(self, message: str, session_id: str) -> Dict[str, Any]:
        # Configuração do Checkpointer Nativo
        conn_string = os.getenv("DATABASE_URL") or os.getenv("ALEMBIC_DATABASE_URL")
        if not conn_string:
             conn_string = "postgresql://pousada_app:ParcerIA19141919@db:5432/pousada_db"
        
        async with AsyncConnectionPool(conn_string, max_size=10) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            # await checkpointer.setup() # Geralmente não necessário se as tabelas já existem
            
            # Carrega histórico para o estado inicial
            db = SessionLocal()
            set_tenant_context(db, self.tenant_id)
            db_msgs = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == session_id, models.ChatMessage.tenant_id == self.tenant_id).order_by(models.ChatMessage.created_at.asc()).all()
            db.close()
            history = []
            for m in db_msgs[-10:]:
                if m.role == "user": history.append(HumanMessage(content=m.content))
                elif m.role == "assistant": history.append(AIMessage(content=m.content))
            history.append(HumanMessage(content=message))

            initial_state = {"messages": history, "tenant_id": self.tenant_id, "session_id": session_id}
            
            # Compila e executa com o checkpointer
            app = self._get_workflow(checkpointer=checkpointer)
            
            # O config 'thread_id' é essencial para o checkpointer carregar o estado anterior
            config = {"configurable": {"thread_id": session_id}}
            
            final_state = await app.ainvoke(initial_state, config=config)

            # Persistência de Fatos (Blackboard)
            from agents.state_manager import StateManager
            sm = StateManager(self.tenant_id)
            updates = self._extract_final_data(final_state)
            sm.update_state(session_id, updates)

            # Resposta
            response = next((m.content for m in reversed(final_state["messages"]) if isinstance(m, AIMessage) and m.content and not m.tool_calls), "Olá!")
            
            db = SessionLocal()
            set_tenant_context(db, self.tenant_id)
            db.add(models.ChatMessage(tenant_id=self.tenant_id, session_id=session_id, role="assistant", content=response))
            db.commit()
            db.close()

            return {"response": response, "session_id": session_id}

    def _extract_final_data(self, state: HotelBookingState) -> Dict[str, Any]:
        updates = {}
        for m in state["messages"]:
            if isinstance(m, ToolMessage):
                try:
                    d = json.loads(m.content)
                    if d.get("guest_id"): updates["guest_id"] = d["guest_id"]
                    if d.get("booking_id"): updates["booking_id"] = d["booking_id"]
                    if d.get("options"): updates["quote_options"] = d["options"]
                except: continue
        
        # Herda do estado atual
        for k in ["check_in", "check_out", "group_size", "room_id", "cpf"]:
            if state.get(k): updates[k] = state[k]
        
        # Inteligência: Se room_id está vazio, mas temos opções e a IA/Humano citou um número
        if not updates.get("room_id"):
            options = state.get("quote_options") or updates.get("quote_options", [])
            all_text = " ".join([m.content for m in state["messages"] if isinstance(m.content, str)]).lower()
            for opt in options:
                rid = str(opt.get("room_id"))
                if rid in all_text:
                    updates["room_id"] = rid
                    logger.info(f"[FSM][EXTRACTOR] Room {rid} detectado via cotação e contexto.")
                    break
                    
        return updates
