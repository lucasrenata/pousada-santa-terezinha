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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

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

def availability_check_logic(tenant_id: int, check_in: str, check_out: str, group_size: int = 1, ages: List[int] = [], check_in_time: str = "14:00", check_out_time: str = "14:00") -> dict:
    """Lógica para consultar vagas e preços. Se idades forem enviadas, já calcula o total exato."""
    """Lógica para consultar vagas e preços sem efetivar reserva."""
    try:
        if not check_in or not check_out:
            return {"error": "Por favor, me informe as datas de chegada e saída para eu verificar aqui! 😊"}
            
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            try:
                ci = datetime.strptime(check_in, "%Y-%m-%d").date()
                co = datetime.strptime(check_out, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "As datas parecem estar em um formato estranho. Pode confirmar o dia e mês?"}

            if ci < date.today():
                return {"error": "Ops! Essa data já passou. Que tal escolhermos uma data futura?"}

            # 1. Busca Eventos para ver se há tarifas especiais
            event = db.query(models.Event).filter(
                models.Event.start_date <= co,
                models.Event.end_date >= ci
            ).first()

            days = calculate_daily_rates_count(ci, co, check_in_time, check_out_time)
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            
            # 2. Busca Quartos Disponíveis
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date > ci,
                models.Booking.check_in_date < co
            ).all()]
            rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()
            
            final_rooms = []
            for r in rooms:
                allowed = True
                # Aplica regras de restrição (Ex: Restrição de Casal em FDS)
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

            # Agrupa para a IA não se perder
            return {
                "available_options": final_rooms,
                "summary": f"Encontrei {len(final_rooms)} quartos disponíveis para {days} diária(s).",
                "pricing_model": settings.get("pousada_pricing_model", "per_person")
            }
    except Exception as e:
        return {"error": f"Tive um probleminha técnico ao olhar as vagas: {str(e)}"}

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

def unified_booking_flow(tenant_id: int, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = [], mode: str = "NORMAL") -> dict:
    """Ferramenta Única: Cria a reserva e gera o PIX em um só passo."""
    total_expected_companions = group_size - 1
    if len(companions) < total_expected_companions:
        return {
            "error": f"Inconsistência de dados: Você informou que são {group_size} pessoas no total, mas só forneceu os dados de {len(companions)} acompanhantes (o titular já está cadastrado). Por favor, peça o Nome e Idade de todos os acompanhantes antes de tentar reservar! 😊"
        }

    # 1. Tenta criar a reserva
    res_booking = booking_creation_logic(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions, mode)
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
# ORQUESTRADOR CENTRAL (AGENTE CUSTOMER)
# =============================================================================

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, base_url: str = ""):
    llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.2)

    # --- BUSCA NOME DA IA E CONFIGURAÇÕES ---
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
    ai_name = settings.get("ai_receptionist_name", "Ana")

    @tool
    def robot_check_availability(check_in: str, check_out: str, group_size: int = 1, ages: List[int] = []) -> dict:
        """Consulta quartos vagos e preços. Datas formato YYYY-MM-DD. 'ages' deve ser uma lista de idades (ex: [30, 28, 5, 12])."""
        print(f"[TOOL_CALL] robot_check_availability: {check_in} a {check_out}, group={group_size}, ages={ages}")
        return availability_check_logic(tenant_id, check_in, check_out, group_size, ages)

    @tool
    def robot_find_guest(cpf: str = "", name: str = "") -> dict:
        """Busca hóspede pelo CPF ou Nome. Se não achar, emite o link de registro."""
        set_tenant_context(db, tenant_id)
        if cpf:
            clean_cpf = "".join(filter(str.isdigit, cpf))
            g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if g: return {"id": g.id, "name": g.name, "cpf": g.document}
        
        prefix = base_url.rstrip("/") if base_url else ""
        link = f"{prefix}/{tenant_id}/registrar?cpf={''.join(filter(str.isdigit, cpf)) if cpf else ''}"
        return {"error": "Hóspede não encontrado.", "registration_link": link}

    @tool
    def robot_pre_validate_checklist(group_size: int, companions: List[dict] = []) -> dict:
        """CHECKLIST: Verifica se você já tem nomes e idades de todos os acompanhantes. Use isso como guia!"""
        print(f"[TOOL_CALL] robot_pre_validate_checklist: group={group_size}, comps={len(companions)}")
        return pre_validation_logic(group_size, companions)

    @tool
    def robot_search_events(query: str) -> dict:
        """Busca eventos (ex: 'Moto Capital', 'PHN') para descobrir datas festivas."""
        set_tenant_context(db, tenant_id)
        events = db.query(models.Event).filter(models.Event.name.ilike(f"%{query}%")).all()
        return {"results": [{"name": e.name, "start": str(e.start_date), "end": str(e.end_date)} for e in events]}

    @tool
    def robot_book_with_payment(guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = []) -> dict:
        """CRIA A RESERVA E GERA O PIX. Requer guest_id, room_id, grupo total e lista de acompanhantes (nome, idade)."""
        print(f"[TOOL_CALL] robot_book_with_payment: guest={guest_id}, room={room_id}, group={group_size}, comps={len(companions)}")
        return unified_booking_flow(tenant_id, guest_id, room_id, check_in, check_out, group_size, companions)

    @tool
    def robot_confirm_payment(booking_id: int, method: str = "pix") -> dict:
        """Confirma que o pagamento foi realizado (ex: após o cliente enviar comprovante) e atualiza para PAGO."""
        print(f"[TOOL_CALL] robot_confirm_payment: booking={booking_id}")
        return confirm_payment_logic(tenant_id, booking_id, method)

    # --- DIAGNÓSTICO DE LOGS ---
    print(f"\n[AI_LOG] Atendimento em curso para Tenant: {tenant_id}")
    print(f"[AI_LOG] Histórico: {len(history)} mensagens anteriores.")

    # --- PERSONA HUMANIZADA ---
    current_date_str = date.today().strftime("%A, %d de %B de %Y")
    sys_msg = SystemMessage(content=f"""Hoje é {current_date_str}.
Você é {ai_name}, a recepcionista virtual super dedicada e amigável da nossa Pousada! ✨
Seu objetivo é tornar a vida do hóspede fácil, oferecendo um atendimento descontraído, acolhedor e eficiente.

DIRETRIZES DE OURO:
1. **Identificação Flexível**: 
   - Se o hóspede estiver apenas **pesquisando preços, disponibilidade ou informações gerais**, responda de forma consultiva e amigável PRIMEIRO. NÃO peça o CPF logo de cara se ele só quer saber o valor.
   - Só peça o CPF quando ele demonstrar que quer realmente **seguir para a reserva** ou se você precisar de dados específicos do cadastro dele.
   - Se não houver cadastro após o CPF, envie o link de registro carinhosamente.
2. **Coleta de Acompanhantes (MUITO IMPORTANTE)**: 
   - O hóspede titular (quem você está conversando) já está no sistema. 
   - TODA outra pessoa citada (esposa, marido, filhos, amigos) é um ACOMPANHANTE.
   - Para CADA acompanhante, você DEVE obter: **Nome Completo** e **Idade**.
   - **Atenção**: Se o hóspede disser "eu, minha esposa e 2 filhos", você precisa de dados de 3 acompanhantes (Esposa + Filho 1 + Filho 2).
   - **Cálculos e Contexto**: 
     - VOCÊ NUNCA FAZ CONTAS E NUNCA REUTILIZA VALORES DE TURNOS ANTERIORES. 
     - Se o hóspede mudar o número de pessoas ou a configuração (ex: "e para 1 pessoa?"), você DEVE chamar o 'robot_check_availability' novamente para obter o novo valor real do sistema.
     - Se o hóspede já informou a idade (ex: "meu filho de 12 anos"), NÃO PERGUNTE A IDADE NOVAMENTE. Peça apenas o nome dele.
4. **Reserva Imortal**: Para criar a reserva, você DEVE usar o 'robot_book_with_payment'. 
   - **ID DO QUARTO**: Use APENAS o 'room_number' retornado pelo robô. NUNCA use o valor ou o nome como ID.
   - Você PRECISA ter o Nome e Idade de TODOS os acompanhantes.
   - **Dica de Ouro**: Use o 'robot_pre_validate_checklist' sempre que tiver dúvida se já coletou tudo. Ele vai te dizer exatamente o que perguntar a seguir!
   - Assim que o checklist estiver 'ready', chame o 'robot_book_with_payment' para finalizar.
   - **Atenção ao Pagamento**: Se o robô retornar 'manual_key' ou 'pix_qr', EXIBA-OS IMEDIATAMENTE.
   - **NUNCA INVENTE CHAVES**: Se o robô não retornar chave nenhuma (status 'pendente_configuracao'), use a 'msg_fallback' fornecida pelo robô. Jamais peça para o cliente "inserir a chave" ou invente dados.
5. **Estilo**: Use emojis, seja leve e acolhedora.
6. **Confirmação Manual**: Se o hóspede enviar comprovante, use 'robot_confirm_payment'.

IMPORTANTE: 
- Sempre repasse a lista exata de idades de TODO o grupo (incluindo adultos como 18+) para o robô de disponibilidade ter o cálculo correto.
- Nunca ignore um acompanhante adulto citado (como esposa/marido).
""")

    tools = [robot_check_availability, robot_find_guest, robot_search_events, robot_pre_validate_checklist, robot_book_with_payment, robot_confirm_payment]
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

    lc_messages = []
    for h in history[-15:]:
        role = h.get("role", "user")
        if role == "user": lc_messages.append(HumanMessage(content=h.get("content", "")))
        elif role == "assistant": lc_messages.append(AIMessage(content=h.get("content", "")))
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        return {"response": final_state["messages"][-1].content}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"Ops! Tive um pequeno tropeço técnico aqui: {str(e)}. Mas já estou me levantando, pode tentar de novo?"}
