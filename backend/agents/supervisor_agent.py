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
from agents.auditor_agent import AuditorAgent

logger = logging.getLogger("SUPERVISOR")

def extract_state_from_history(messages: List[Any]) -> Dict[str, Any]:
    """
    Extrai check-in, check-out, group_size, CPF e room_id das mensagens de forma robusta.
    """
    from utils.date_parser import extract_dates_from_text, extract_group_size_from_text
    
    # Analisa as últimas 6 mensagens para manter o contexto vivo
    recent_messages = messages[-6:]
    full_text = " ".join([str(m.content) for m in recent_messages if hasattr(m, 'content')])
    
    # Extração de Datas
    ci, co = extract_dates_from_text(full_text)
    
    # Extração de Pessoas (foca na última mensagem para evitar somas erradas)
    last_user_msg = next((str(m.content) for m in reversed(messages) if hasattr(m, 'content') and not isinstance(m, AIMessage)), "")
    gs = extract_group_size_from_text(last_user_msg) or extract_group_size_from_text(full_text)
    
    # Extração de CPF
    cpf_match = re.search(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', full_text) or re.search(r'\b\d{11}\b', full_text)
    cpf = cpf_match.group(0).replace(".", "").replace("-", "") if cpf_match else None
    
    # Extração de Quarto
    room_match = re.search(r'\b(?:quarto|número|room|nº|#)\s*[:#]?\s*(\d{3})\b', full_text, re.IGNORECASE)
    room_id = room_match.group(1) if room_match else None
    
    state = {}
    if ci: state["check_in"] = ci
    if co: state["check_out"] = co
    if gs: state["group_size"] = gs
    if cpf: state["cpf"] = cpf
    if room_id: state["room_id"] = room_id
    
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
        extracted_data = extract_state_from_history(state["messages"])
        logger.info(f"[FSM][EXTRACTOR] Novas entidades: {extracted_data}")
        return extracted_data

    def fsm_router(self, state: HotelBookingState) -> str:
        last_msg = state["messages"][-1].content.lower()
        
        # 1. Rota de FAQ (Prioridade de dúvida do hóspede)
        faq_keywords = [
            "pet", "animal", "animais", "gato", "cachorro", "dog", "cat",
            "horário", "piscina", "café", "estacionamento", "regra", "política", "cancelamento"
        ]
        if any(kw in last_msg for kw in faq_keywords): return "faq"
        
        # 2. Rota de PAGAMENTO (Se existe reserva E intenção de pagar)
        if state.get("booking_id"):
            payment_keywords = ["pagar", "pagamento", "pix", "comprovante", "cartão", "link", "valor", "sinal", "depósito", "como eu pago", "arquivo", "enviado", "pago"]
            is_payment_intent = any(kw in last_msg for kw in payment_keywords) or \
                               last_msg in ["sim", "quero", "ok", "pode ser", "claro", "manda", "envia", "por favor", "com certeza", "bora"]
            
            if is_payment_intent:
                logger.info(f"[FSM][ROUTER] Reserva #{state['booking_id']} + Intenção detectada. Direcionando para PAGAMENTO.")
                return "pagamento"
        
        # 3. Rota de RESERVAS (Fluxo padrão de venda/seleção ou ajustes)
        return "reservas"

    async def reservas_node(self, state: HotelBookingState):
        from agents.specialists.reservas_agent import build_reservas_graph
        graph = build_reservas_graph(self.tenant_id, state["session_id"])
        
        board_msg = self._build_blackboard_msg(state)
        input_messages = [board_msg] + state["messages"]
        
        logger.info(f"[FSM][RESERVAS] Iniciando sub-grafo...")
        res = await graph.ainvoke({"messages": input_messages})
        
        # --- SCHEMA VALIDATOR (SOLUÇÃO 2) ---
        last_ai_msg = res["messages"][-1].content
        if "robot_calculate_quote" in str(res["messages"]) and "R$" not in str(last_ai_msg):
            logger.warning("[FSM][RESERVAS] Resposta não estruturada detectada. Forçando re-formatação.")
            # Se o especialista esqueceu de falar os preços, o Supervisor injeta os dados do blackboard
            if state.get("quote_options"):
                last_ai_msg += "\n[VALIDATOR] Sistema: Use estes dados de cotação: " + str(state["quote_options"])

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
        from datetime import datetime
        now = datetime.now()
        current_date_info = f"HOJE: {now.strftime('%d/%m')}/2026 ({now.strftime('%A')})"
        
        # --- QUADRO DE FATOS ---
        facts = [current_date_info, "ANO: 2026"]
        has_dates = state.get("check_in") and state.get("check_out")
        has_group = state.get("group_size")
        has_quote = state.get("quote_options") # Se já fizemos cotação
        has_cpf = state.get("cpf")
        has_guest = state.get("guest_id")
        has_booking = state.get("booking_id")
        
        if state.get("check_in"): facts.append(f"- CHECK-IN: {state['check_in']}")
        if state.get("check_out"): facts.append(f"- CHECK-OUT: {state['check_out']}")
        if state.get("group_size"): facts.append(f"- HÓSPEDES: {state['group_size']}")
        if state.get("cpf"): facts.append(f"- CPF: {state['cpf']}")
        if state.get("guest_id"): facts.append(f"- CADASTRO: LOCALIZADO (ID {state['guest_id']})")
        if state.get("booking_id"): facts.append(f"- RESERVA: #{state['booking_id']}")

        # --- ESTRATÉGIA DO ROTEIRO DE 14 PASSOS ---
        strategy = "🎯 ESTRATÉGIA DO ROTEIRO: "
        if has_booking:
            strategy += "Reserva criada! Explique o pagamento do sinal e entregue o PIX/Link (Passos 11-14)."
        elif has_guest and has_quote:
            strategy += "Cadastro OK! Faça a confirmação final de Quarto/Valor/Pessoas e crie a reserva (Passos 9-10)."
        elif has_cpf and not has_guest:
            strategy += "CPF fornecido mas sem cadastro. Forneça o LINK DE CADASTRO agora (Passo 7)."
        elif has_quote:
            strategy += "Valores entregues! Se o hóspede der o OK, peça o CPF do responsável (Passos 5-6)."
        elif has_dates and has_group:
            strategy += "Dados prontos. Chame `robot_calculate_quote` e entregue os valores (Passo 4)."
        elif has_dates:
            strategy += "Temos datas. Pergunte agora a quantidade de pessoas e idades (Passo 3)."
        else:
            strategy += "Início do funil. Dê as boas-vindas e pergunte as datas (Passos 1-2)."

        content = f"📍 QUADRO DE FATOS:\n" + "\n".join(facts)
        content += f"\n\n{strategy}\n"
        content += "\n⚠️ REGRAL GERAL: Nunca pule a ordem. Só peça CPF após o hóspede aceitar os valores."
            
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
            
            # --- FILTRO DE MENSAGENS RECENTES (ÚLTIMA 1 HORA) ---
            from datetime import datetime, timedelta
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            db_msgs = db.query(models.ChatMessage).filter(
                models.ChatMessage.session_id == session_id, 
                models.ChatMessage.tenant_id == self.tenant_id,
                models.ChatMessage.created_at >= one_hour_ago
            ).order_by(models.ChatMessage.created_at.asc()).all()
            db.close()
            history = []
            # Filtro anti-repetição de saudações no histórico do banco
            greeting_patterns = ["a paz,", "bem vindo a pousada", "como posso ajudar hoje?", "olá! encontrei as informações"]
            
            for m in db_msgs[-10:]:
                content_lower = m.content.lower()
                # Se for uma saudação automática repetida, ignora para não confundir o modelo
                if any(p in content_lower for p in greeting_patterns) and m.role == "assistant":
                    continue
                    
                if m.role == "user": 
                    history.append(HumanMessage(content=m.content))
                elif m.role == "assistant": 
                    history.append(AIMessage(content=m.content))
            
            # Adiciona a mensagem atual (garantindo que não seja um eco)
            if not any(p in message.lower() for p in greeting_patterns):
                history.append(HumanMessage(content=message))
            else:
                # Se for apenas uma saudação, trata como início limpo
                history = [HumanMessage(content=message)]

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

            # Resposta: Busca a última mensagem de texto (AIMessage) gerada NESTE turno
            response = ""
            for m in reversed(final_state["messages"]):
                if isinstance(m, AIMessage) and m.content:
                    content = ""
                    if isinstance(m.content, str):
                        content = m.content.strip()
                    elif isinstance(m.content, list):
                        content = " ".join([c["text"] for c in m.content if isinstance(c, dict) and "text" in c]).strip()
                    
                    if content and not content.startswith("{"):
                        # Se a resposta for um 'Frankenstein' (repetindo saudações), limpa
                        if "A paz," in content and len(final_state["messages"]) > 3:
                            # Se não for o início da conversa, remove a saudação repetida
                            content = re.sub(r"^(A paz,.*?Como posso te ajudar hoje\?)\s*", "", content, flags=re.IGNORECASE | re.DOTALL)
                        
                        response = content.strip()
                        break

            if not response:
                logger.warning(f"[SUPERVISOR] Especialista não gerou texto. Iniciando Resgate de Resposta...")
                try:
                    # Tenta uma chamada rápida de síntese para não deixar o usuário no vácuo
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    rescue_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=self.api_key, temperature=0.7)
                    
                    # Constrói um prompt de resumo baseado no Blackboard e últimas mensagens
                    recap_prompt = f"""Você é o SUPERVISOR da Pousada. 
O especialista técnico executou ações (verificou preços, disponibilidade ou criou reserva), mas esqueceu de falar com o hóspede.

DADOS ATUAIS DO SISTEMA: {updates}

Com base no histórico e nos dados acima, dê uma resposta CURTA, NATURAL e DIRETA para o hóspede informando o que foi feito ou o que foi encontrado. 

⚠️ REGRA DE OURO: NÃO FAÇA CONTAS. Use apenas os valores que aparecem em 'DADOS ATUAIS DO SISTEMA'. Se o sistema diz que o total é R$ 100, diga que é R$ 100. Nunca tente somar ou multiplicar por conta própria.
Seja acolhedor."""
                    
                    rescue_msg = await rescue_llm.ainvoke([
                        SystemMessage(content=recap_prompt),
                        HumanMessage(content="O que você encontrou/fez para mim?")
                    ])
                    response = rescue_msg.content.strip()
                    logger.info(f"[SUPERVISOR] Resgate concluído com sucesso: {response[:50]}...")
                except Exception as e:
                    logger.error(f"[SUPERVISOR] Falha no Resgate: {e}")
                    response = "Olá! Já processei sua solicitação no sistema. Como posso te ajudar com os próximos passos?"
            
            # --- SANITIZAÇÃO DE LINKS MARKDOWN ---
            # Remove qualquer espaço vazio dentro da sintaxe de link do markdown [texto]( ur l ) -> [texto](url)
            # Isso garante que a UI frontend (react-markdown) renderize corretamente como Botão.
            response = re.sub(
                r'\[(.*?)\]\(\s*(.*?)\s*\)', 
                lambda m: f"[{m.group(1)}]({m.group(2).replace(' ', '')})", 
                response
            )

            # 🔍 AUDITORIA DE QUALIDADE (Anti-Falha de Ferramentas)
            auditor = AuditorAgent(self.tenant_id)
            last_action = None
            action_details = {}
            
            if updates.get("booking_id"):
                last_action = "create_booking"
                action_details = {"booking_id": updates["booking_id"]}
            elif updates.get("guest_id"):
                last_action = "identify_guest"
                action_details = {"guest_id": updates["guest_id"]}
                
            response = await auditor.audit_response(response, {
                "last_action": last_action,
                "action_details": action_details
            })
            
            db = SessionLocal()
            set_tenant_context(db, self.tenant_id)
            db.add(models.ChatMessage(tenant_id=self.tenant_id, session_id=session_id, role="assistant", content=response))
            db.commit()
            db.close()

            return {"response": response, "session_id": session_id, "facts": updates}

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
