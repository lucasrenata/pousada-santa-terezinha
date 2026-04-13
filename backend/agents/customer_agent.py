import json
import os
from sqlalchemy.orm import Session
import models
from database import SessionLocal, set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# =============================================================================
# MOTOR DE CÁLCULO UNIFICADO
# =============================================================================

def calculate_booking_quote(db, tenant_id, room_id, check_in_date, check_out_date, group_size, ages: List[int] = []):
    """Fonte única de verdade para cálculos de reserva."""
    set_tenant_context(db, tenant_id)
    ci = check_in_date
    co = check_out_date
    days = calculate_daily_rates_count(ci, co)
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
    active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
    room = db.query(models.Room).get(room_id)
    daily_base = room.price_per_night if room else 100.0

    # Busca Eventos para ver se há tarifas especiais
    event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()

    total_amount = 0.0
    note_parts = []
    
    # Se não informou idades suficientes, completa com adultos (18)
    full_ages = ages[:group_size]
    if len(full_ages) < group_size:
        full_ages += [18] * (group_size - len(full_ages))

    # Lógica de Preço de Evento vs Normal
    if event and (event.daily_rate_single > 0 or event.daily_rate_couple > 0):
        adults = len([age for age in full_ages if age >= 13])
        children = len([age for age in full_ages if 7 <= age < 13])
        
        if adults == 1 and event.daily_rate_single > 0:
            total_amount = (event.daily_rate_single + (children * event.daily_rate_child)) * days
            note_parts.append(f"Tarifa Single Evento: R${event.daily_rate_single}")
        elif adults >= 2 and event.daily_rate_couple > 0:
            extras = adults - 2
            total_amount = (event.daily_rate_couple + (extras * event.daily_rate_extra) + (children * event.daily_rate_child)) * days
            note_parts.append(f"Tarifa Casal Evento: R${event.daily_rate_couple}")
        else:
            total_amount = (event.daily_rate or 100.0) * group_size * days
            note_parts.append(f"Tarifa Geral Evento: R${event.daily_rate}")
    else:
        pricing = calculate_reservation_total(daily_base, days, full_ages, settings=settings)
        total_amount = pricing["total"]
        note_parts.append(f"Tarifa Padrão: R${daily_base}")

    # Ajustes de Regras (FDS)
    fds_rule = next((r for r in active_rules if r.name == "Tarifa Fim de Semana"), None)
    if fds_rule:
        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
        if has_weekend:
            mult = float(fds_rule.config.get("multiplier", 1.2))
            total_amount *= mult
            note_parts.append(f"Ajuste FDS (x{mult})")

    return {
        "total": total_amount,
        "days": days,
        "notes": " | ".join(note_parts),
        "event_name": event.name if event else None,
        "pricing_model": settings.get("pousada_pricing_model", "per_person")
    }

# =============================================================================
# MICRO-LÓGICAS: ATIVIDADES DA RECEPÇÃO VIRTUAL
# =============================================================================

def find_guest_logic(tenant_id: int, cpf: str = "", name: str = "", base_url: str = "") -> dict:
    """Lógica atômica para buscar ou linkar registro de hóspede."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        if cpf:
            clean_cpf = "".join(filter(str.isdigit, cpf))
            g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if g: return {"id": g.id, "name": g.name, "cpf": g.document}
        
        prefix = base_url.rstrip("/") if base_url else ""
        link = f"{prefix}/{tenant_id}/registrar?cpf={''.join(filter(str.isdigit, cpf)) if cpf else ''}"
        return {"error": "Hóspede não encontrado.", "registration_link": link}

def availability_check_logic(tenant_id: int, check_in: str, check_out: str, group_size: int = 1, ages: List[int] = [], check_in_time: str = "14:00", check_out_time: str = "14:00") -> dict:
    """Lógica atômica para consultar vagas e preços. Se idades forem enviadas, já calcula o total exato."""
    try:
        if not check_in or not check_out:
            return {"error": "Por favor, me informe as datas de chegada e saída para eu verificar aqui! 😊"}
            
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            
            # --- SMART DATE PARSER (SENIOR VERSION) ---
            now = datetime.now()
            def parse_smart_date(date_str):
                date_str = date_str.strip()
                try:
                    target_date = None
                    if "/" in date_str:
                        parts = date_str.split("/")
                        day = int(parts[0])
                        month = int(parts[1])
                        year = int(parts[2]) if len(parts) > 2 else now.year
                        target_date = date(year, month, day)
                        
                        # Se a data for no passado e o ano não foi especificado, assume o próximo ano
                        if len(parts) <= 2 and target_date < now.date():
                            target_date = date(year + 1, month, day)
                    else:
                        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    return target_date
                except:
                    return None

            ci = parse_smart_date(check_in)
            co = parse_smart_date(check_out)

            if not ci or not co:
                return {"error": f"Formato de data inválido ({check_in} a {check_out}). Use DD/MM ou AAAA-MM-DD."}

            print(f"[TOOL_CALL] robot_check_availability: {ci} to {co}, group={group_size}")

            if ci < now.date():
                return {"error": "Ops! Essa data já passou. Que tal escolhermos uma data futura?"}

            # 1. Busca quartos disponíveis e calcula orçamento unificado
            days = calculate_daily_rates_count(ci, co, check_in_time, check_out_time)
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()]
            rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()
            
            final_rooms = []
            for r in rooms:
                allowed = True
                couple_rule = next((rule for rule in active_rules if rule.name == "Restrição de Casal"), None)
                if couple_rule and group_size == 2:
                    restricted_rooms = [rid.strip() for rid in couple_rule.config.get("room_ids", "").split(",") if rid.strip()]
                    if r.id in restricted_rooms:
                        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                        if has_weekend: allowed = False
                
                if allowed and r.max_capacity >= group_size:
                    quote = calculate_booking_quote(db, tenant_id, r.id, ci, co, group_size, ages)
                    final_rooms.append({
                        "room_number": r.id, 
                        "type": r.type or "Quarto",
                        "capacity": r.max_capacity, 
                        "total_quote": quote["total"],
                        "notes": quote["notes"]
                    })

            print(f"[TOOL_RESULT] robot_check_availability: {len(final_rooms)} quartos encontrados.")
            return {
                "available_options": final_rooms,
                "summary": f"Encontrei {len(final_rooms)} quartos disponíveis.",
                "pricing_model": settings.get("pousada_pricing_model", "per_person")
            }
    except Exception as e:
        return {"error": f"Erro na consulta de disponibilidade: {str(e)}"}

def search_events_logic(tenant_id: int, query: str) -> dict:
    """Lógica atômica para busca de eventos festivos."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        events = db.query(models.Event).filter(models.Event.name.ilike(f"%{query}%")).all()
        return {"results": [{"name": e.name, "start": str(e.start_date), "end": str(e.end_date)} for e in events]}

def pre_validation_logic(group_size: int, companions: List[dict] = []) -> dict:
    """Analisa se os dados coletados pela IA estão completos para uma reserva."""
    total_expected = group_size - 1 # O titular não conta como acompanhante
    missing = []
    
    current_count = len(companions)
    if current_count < total_expected:
        diff = total_expected - current_count
        missing.append(f"Dados de mais {diff} acompanhante(s)")
    
    for i, c in enumerate(companions):
        name = c.get('name', '').strip()
        age = c.get('age')
        
        desc = f"Acompanhante {i+1}"
        if not name: missing.append(f"Nome do {desc}")
        if age is None: missing.append(f"Idade do {desc}")

    if not missing:
        return {"status": "ready", "message": "Tudo pronto! Pode prosseguir com a reserva. ✅"}
    else:
        return {
            "status": "incomplete",
            "missing": missing,
            "instruction": "Você ainda precisa coletar esses dados com o hóspede antes de finalizar."
        }

def unified_booking_flow(tenant_id: int, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List = [], mode: str = "NORMAL") -> dict:
    """Ferramenta Única: Cria a reserva e gera o PIX em um só passo."""
    
    # --- NORMALIZAÇÃO DE ACOMPANHANTES (SENIOR FIX) ---
    # Se a IA enviar uma lista de nomes (strings), converte para objetos com idade padrão 18
    normalized_companions = []
    for c in companions:
        if isinstance(c, str):
            normalized_companions.append({"name": c, "age": 18})
        elif isinstance(c, dict):
            normalized_companions.append(c)
    
    total_expected_companions = group_size - 1
    if len(normalized_companions) < total_expected_companions:
        return {
            "error": f"Faltam dados: São {group_size} pessoas, mas só identifiquei {len(normalized_companions)} acompanhante(s). Preciso do Nome e Idade de cada um."
        }

    # 1. Tenta criar a reserva
    res_booking = booking_creation_logic(tenant_id, guest_id, room_id, check_in, check_out, group_size, normalized_companions, mode)
    if "error" in res_booking:
        return res_booking

    # 2. Se deu certo, gera o pagamento imediatamente
    res_payment = payment_info_logic(tenant_id, res_booking["booking_id"])
    
    return {
        "success": True,
        "booking_details": res_booking,
        "payment_details": res_payment,
        "message": "Reserva criada com sucesso e pagamento gerado! 🎉"
    }

def booking_creation_logic(tenant_id: int, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = [], mode: str = "NORMAL") -> dict:
    """Lógica para efetivar a reserva no banco de dados."""
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            
            guest = db.query(models.Guest).get(guest_id)
            if not guest: return {"error": "Hóspede principal não localizado."}
            
            # Recupera idades para o cálculo unificado
            ages = [guest.age or 18] + [int(c.get('age', 18)) for c in companions]
            quote = calculate_booking_quote(db, tenant_id, room_id, ci, co, group_size, ages)

            # Criação do Registro
            booking = models.Booking(
                guest_id=guest_id, room_id=room_id, check_in_date=ci, check_out_date=co,
                total_guests=group_size, total_amount=quote["total"], 
                mode=models.BookingMode.NORMAL if mode == "NORMAL" else models.BookingMode.CARAVANA,
                status=models.BookingStatus.PENDENTE,
                daily_rate=quote["total"] / (quote["days"] * group_size) if quote["days"] > 0 and group_size > 0 else 0,
                notes=quote["notes"]
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)

            # Adiciona acompanhantes
            for c in companions:
                age_val = int(c.get('age', 18))
                db.add(models.Companion(booking_id=booking.id, name=c['name'], age=age_val))
            
            db.commit()
            return {"success": True, "booking_id": booking.id, "total": quote["total"], "notes": quote["notes"]}
    except Exception as e:
        return {"error": f"Erro ao finalizar a reserva: {str(e)}"}

def payment_info_logic(tenant_id: int, booking_id: int) -> dict:
    """Lógica para gerar dados de pagamento (Mercado Pago + Fallback Manual)."""
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking: return {"error": "Reserva não localizada."}

            config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == tenant_id, models.TenantConfig.is_active == True).first()
            manual_key = config.manual_pix_key if config else None

            # Tenta gerar PIX via Mercado Pago
            qr_data = None
            try:
                from payments.mercadopago_service import MercadoPagoService
                from routers.payments import get_tenant_mp_token
                
                token = get_tenant_mp_token(db, tenant_id)
                if token:
                    mp = MercadoPagoService()
                    description = f"Reserva #{booking.id} - {booking.guest.name}"
                    payer = {
                        "email": booking.guest.email or "guest@test.com",
                        "first_name": booking.guest.name.split()[0],
                        "last_name": booking.guest.name.split()[-1] if " " in booking.guest.name else "Hóspede",
                        "identification": {"type": "CPF", "number": "".join(filter(str.isdigit, booking.guest.document or "19119119100"))}
                    }
                    res = mp.create_pix_payment(token, tenant_id, booking.total_amount, description, {"booking_id": booking.id}, payer=payer)
                    poi = (res.get("response") or {}).get("point_of_interaction", {}).get("transaction_data", {})
                    qr_data = {"image": poi.get("qr_code_base64"), "code": poi.get("qr_code")}
                    if qr_data.get("code"):
                        print(f"[PAYMENT_LOG] PIX Gerado via Mercado Pago para Reserva #{booking_id}")
            except Exception as e:
                print(f"[PAYMENT_LOG] Falha no Mercado Pago: {str(e)}")

            # Se falhou MP, tenta Manual no TenantConfig ou SystemSetting
            if not qr_data or not qr_data.get("code"):
                if not manual_key:
                    # Fallback para Settings Globais
                    global_pix = db.query(models.SystemSetting).filter(models.SystemSetting.key == "pousada_pix_key").first()
                    manual_key = global_pix.value if global_pix else None
                    if manual_key:
                        print(f"[PAYMENT_LOG] Usando Chave PIX Global para Reserva #{booking_id}")
                else:
                    print(f"[PAYMENT_LOG] Usando Chave PIX do Estabelecimento para Reserva #{booking_id}")

            status = "pronto" if (qr_data and qr_data.get("code")) or manual_key else "pendente_configuracao"

            return {
                "booking_id": booking_id,
                "status": status,
                "total": booking.total_amount,
                "pix_qr": qr_data,
                "manual_key": manual_key,
                "msg_fallback": "Reserva garantida! Mas tive um probleminha para gerar sua chave agora. Nossa equipe entrará em contato em breve! 😊" if status == "pendente_configuracao" else None,
                "instructions": "Envie o comprovante para acelerar a confirmação! 😊"
            }
    except Exception as e:
        return {"error": f"Erro ao processar pagamento: {str(e)}"}

def confirm_payment_logic(tenant_id: int, booking_id: int, method: str = "pix") -> dict:
    """Lógica para confirmar pagamento e atualizar status da reserva."""
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking: return {"error": "Reserva não localizada."}

            booking.status = models.BookingStatus.CONFIRMADO
            booking.payment_status = models.PaymentStatus.PAGO
            
            # Lança no financeiro
            rev = models.Revenue(
                description=f"Pagamento Reserva #{booking.id} ({method.upper()})",
                amount=booking.total_amount,
                category=models.RevenueCategory.HOSPEDAGEM,
                payment_method=method.lower(),
                booking_id=booking.id,
                created_at=datetime.now()
            )
            db.add(rev)
            db.commit()
            return {"success": True, "message": f"Reserva #{booking.id} CONFIRMADA e PAGA com sucesso! 🎉"}
    except Exception as e:
        return {"error": f"Erro ao confirmar pagamento: {str(e)}"}

# =============================================================================
# OPERATIONAL MEMORY: APRENDIZADO CONTÍNUO
# =============================================================================

def get_operational_memory(tenant_id: int, guest_id: int = None) -> str:
    """Recupera fatos e aprendizados relevantes do banco de dados."""
    with SessionLocal() as db:
        query = db.query(models.TenantMemory).filter(models.TenantMemory.tenant_id == tenant_id, models.TenantMemory.is_active == True)
        if guest_id:
            # Pega memórias gerais E específicas do hóspede
            from sqlalchemy import or_
            query = query.filter(or_(models.TenantMemory.guest_id == guest_id, models.TenantMemory.guest_id == None))
        
        memories = query.order_by(models.TenantMemory.importance.desc()).limit(10).all()
        if not memories: return ""
        
        text = "\n[MEMÓRIA OPERACIONAL / APRENDIZADOS]:\n"
        for m in memories:
            text += f"- {m.content}\n"
        return text

def store_operational_memory_logic(tenant_id: int, content: str, category: str = "geral", guest_id: int = None, importance: int = 1) -> dict:
    """Lógica para salvar novos aprendizados no banco."""
    with SessionLocal() as db:
        new_mem = models.TenantMemory(
            tenant_id=tenant_id, guest_id=guest_id, 
            category=category, content=content, importance=importance
        )
        db.add(new_mem)
        db.commit()
        return {"success": True, "message": "Aprendizado registrado com sucesso na minha memória de longo prazo! 🧠"}

def convert_history_to_langchain(history: list):
    """Converte o histórico do DB para o formato LangChain, preservando chamadas de ferramentas."""
    lc_messages = []
    # Pegamos os últimos 15 turnos para manter o contexto operacional sem estourar tokens
    for h in history[-15:]:
        role = h.get("role")
        content = h.get("content", "")
        tool_calls = h.get("tool_calls") # Se vier do histórico do DB como JSON
        
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            if tool_calls:
                lc_messages.append(AIMessage(content=content, tool_calls=tool_calls))
            else:
                lc_messages.append(AIMessage(content=content))
        elif role == "tool":
            lc_messages.append(ToolMessage(content=content, tool_call_id=h.get("tool_call_id", "")))
            
    return lc_messages

# =============================================================================
# ORQUESTRADOR CENTRAL (AGENTE CUSTOMER)
# =============================================================================

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, base_url: str = ""):
    # --- SELEÇÃO DE MODELO (OPENAI VS GEMINI) ---
    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")
    
    if google_key and gemini_model:
        llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)
        print(f"[AI_LOG] Usando Google Gemini: {gemini_model}")
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.2)
        print(f"[AI_LOG] Usando OpenAI: gpt-4o-mini")

    # --- BUSCA NOME DA IA E CONFIGURAÇÕES ---
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
    ai_name = settings.get("ai_receptionist_name", "Ana")

    @tool
    def robot_check_availability(check_in: str, check_out: str, group_size: int = 1, ages: List[int] = []) -> dict:
        """Micro-robô para consultar vagas e preços. Datas formato DD/MM ou YYYY-MM-DD. 'ages' é lista de idades."""
        return availability_check_logic(tenant_id, check_in, check_out, group_size, ages)

    @tool
    def robot_find_guest(cpf: str = "", name: str = "") -> dict:
        """Micro-robô para identificar hóspedes pelo CPF ou Nome."""
        return find_guest_logic(tenant_id, cpf, name, base_url)

    @tool
    def robot_pre_validate_checklist(group_size: int, companions: List[dict] = []) -> dict:
        """Micro-robô CHECKLIST: Verifica se você já tem nomes e idades de todos os acompanhantes."""
        return pre_validation_logic(group_size, companions)

    @tool
    def robot_search_events(query: str) -> dict:
        """Micro-robô especializado em descobrir datas de EVENTOS festivos."""
        return search_events_logic(tenant_id, query)

    @tool
    def robot_book_with_payment(guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = []) -> dict:
        """Micro-robô FINALIZADOR: Cria a reserva e gera o PIX em um só passo."""
        return unified_booking_flow(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions)

    @tool
    def robot_confirm_payment(booking_id: int, method: str = "pix") -> dict:
        """Micro-robô financeiro: Confirma pagamentos e libera a reserva."""
        return confirm_payment_logic(tenant_id, booking_id, method)

    @tool
    def robot_record_knowledge(content: str, category: str = "geral", importance: int = 1, guest_id: int = None) -> dict:
        """Micro-robô de APRENDIZADO: Salva fatos importantes ou preferências do hóspede na memória."""
        print(f"[TOOL_CALL] robot_record_knowledge: {content[:50]}...")
        return store_operational_memory_logic(tenant_id, content, category, guest_id, importance)

    # --- MEMÓRIA E DIAGNÓSTICO ---
    # Tenta identificar o hóspede no histórico para carregar a memória específica
    current_guest_id = None
    for h in reversed(history):
        if h.get("guest_id"): 
            current_guest_id = h["guest_id"]
            break
            
    op_memory = get_operational_memory(tenant_id, current_guest_id)
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

5. INTELIGÊNCIA DE DATAS:
   - O robô entende formatos brasileiros (DD/MM). Se hoje é Dezembro e o hóspede diz "Janeiro", o robô saberá que é o ano seguinte.

ESTILO: Profissional, eficiente e acolhedor, mas focado na conclusão correta da transação.
""")

    tools = [
        robot_check_availability, robot_find_guest, robot_search_events, 
        robot_pre_validate_checklist, robot_book_with_payment, robot_confirm_payment,
        robot_record_knowledge
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
        return {"response": final_state["messages"][-1].content}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"Ops! Tive um pequeno tropeço técnico aqui: {str(e)}. Mas já estou me levantando, pode tentar de novo?"}
