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

def extract_state_from_history(messages: List[Any]) -> Dict[str, Any]:
    """
    Extrai check-in, check-out, group_size e CPF das mensagens.
    Foca nas mensagens recentes para evitar confusão com dados antigos.
    """
    from utils.date_parser import extract_dates_from_text
    
    # Pega apenas as últimas 4 mensagens para contexto de extração
    recent_messages = messages[-4:]
    full_text = " ".join([m.content for m in recent_messages if isinstance(m, HumanMessage) and isinstance(m.content, str)])
    
    # Prioriza a ÚLTIMA mensagem para group_size para evitar "2" + "2" = 22
    last_user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    state = {}
    
    # Datas
    dates = extract_dates_from_text(full_text)
    if dates:
        state["check_in"] = dates[0]
        if len(dates) > 1:
            state["check_out"] = dates[1]
            
    # Group Size (Sanidade: 1 a 15 pessoas)
    group_match = re.search(r"(\d+)\s*(pess|adult|hosp|alguém)", last_user_msg.lower())
    if not group_match:
        group_match = re.search(r"^\s*(\d+)\s*$", last_user_msg) # Match número isolado "2"
        
    if group_match:
        val = int(group_match.group(1))
        if 1 <= val <= 15: # Limite de sanidade
            state["group_size"] = val
            
    # CPF
    cpf_match = re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", full_text)
    if cpf_match:
        state["cpf"] = cpf_match.group(0).replace(".", "").replace("-", "")

    # Detecção de room_id (ex: "quarto 102", "quarto número 101", "número 303")
    room_match = re.search(r'\b(?:quarto|número|room|nº|#)\s*[:#]?\s*(\d{3})\b', full_text, re.IGNORECASE)
    if room_match: state["room_id"] = room_match.group(1)
    
    return state

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
        
        # 1. Rota de FAQ (Prioridade de dúvida do hóspede)
        faq_keywords = [
            "pet", "animal", "animais", "gato", "cachorro", "dog", "cat",
            "horário", "piscina", "café", "estacionamento", "regra", "política", "cancelamento"
        ]
        if any(kw in last_msg for kw in faq_keywords): return "faq"
        
        # 2. Rota de PAGAMENTO (Se já existe reserva criada) - DETERMINÍSTICO
        if state.get("booking_id"): 
            logger.info(f"[FSM][ROUTER] Reserva #{state['booking_id']} detectada. Direcionando para PAGAMENTO.")
            return "pagamento"
        
        # 3. Rota de RESERVAS (Fluxo padrão de venda/seleção)
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
        is_complete = False
        if state.get("check_in") and state.get("check_out") and state.get("group_size"):
            is_complete = True
            b.append(f"- PERÍODO: {state['check_in']} a {state['check_out']}")
            b.append(f"- HÓSPEDES: {state['group_size']}")
        
        if state.get("room_id"): b.append(f"- QUARTO SELECIONADO: {state['room_id']}")
        if state.get("guest_id"): b.append(f"- HÓSPEDE CADASTRADO ID: {state['guest_id']}")
        if state.get("booking_id"): b.append(f"- RESERVA CRIADA: #{state['booking_id']}")
        
        content = "📍 QUADRO DE ATENDIMENTO:\n" + ("\n".join(b) if b else "(Vazio)")
        
        if is_complete:
            content += "\n\n⚠️ INSTRUÇÃO CRÍTICA: Você já tem os dados da reserva. NÃO dê boas-vindas, NÃO pergunte datas. Chame a ferramenta de cotação ou avance para identificação do CPF imediatamente."
            
        return SystemMessage(content=content)

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
            # Resposta: Busca a última mensagem de texto (AIMessage) de forma robusta
            response = ""
            for m in reversed(final_state["messages"]):
                if isinstance(m, AIMessage) and m.content:
                    # Priorizamos mensagens sem tool_calls, mas se tiver conteúdo, usamos
                    content = m.content.strip()
                    if content and not content.startswith("{"): # Evita vazar JSON bruto se houver
                        response = content
                        break

            if not response:
                response = "Encontrei as informações para você! Como podemos prosseguir?"
                logger.error(f"[SUPERVISOR] Falha ao encontrar resposta de texto. Histórico: {final_state['messages'][-3:]}")
            
            db = SessionLocal()
            set_tenant_context(db, self.tenant_id)
            db.add(models.ChatMessage(tenant_id=self.tenant_id, session_id=session_id, role="assistant", content=response))
            db.commit()
            db.close()

            return {"response": response, "session_id": session_id}

    def _extract_final_data(self, state: HotelBookingState) -> Dict[str, Any]:
        updates = {}
        # 1. Inteligência via JSON (tool_calls) - PRECISÃO MÁXIMA
        for m in state["messages"]:
            if isinstance(m, AIMessage) and m.tool_calls:
                for call in m.tool_calls:
                    args = call.get("args", {})
                    if args.get("check_in"): updates["check_in"] = args["check_in"]
                    if args.get("check_out"): updates["check_out"] = args["check_out"]
                    if args.get("group_size"): updates["group_size"] = args["group_size"]
                    if args.get("room_id"): updates["room_id"] = str(args["room_id"])
                    if args.get("cpf"): updates["cpf"] = str(args["cpf"]).replace(".", "").replace("-", "")

            # 2. Respostas das Ferramentas (ToolMessage)
            if isinstance(m, ToolMessage):
                try:
                    d = json.loads(m.content)
                    if d.get("guest_id"): updates["guest_id"] = d["guest_id"]
                    if d.get("booking_id"): updates["booking_id"] = d["booking_id"]
                    if d.get("options"): updates["quote_options"] = d["options"]
                except: continue
        
        # 3. Herda do estado atual (Fallback)
        for k in ["check_in", "check_out", "group_size", "room_id", "cpf"]:
            if state.get(k) and not updates.get(k):
                updates[k] = state[k]
        
        # 4. Detecção de Room ID via Contexto se estiver vazio
        if not updates.get("room_id"):
            options = updates.get("quote_options") or state.get("quote_options", [])
            all_text = " ".join([m.content for m in state["messages"] if isinstance(m.content, str)]).lower()
            for opt in options:
                rid = str(opt.get("room_id"))
                if rid in all_text:
                    updates["room_id"] = rid
                    logger.info(f"[FSM][EXTRACTOR] Room {rid} detectado via cotação.")
                    break
                    
        return updates
