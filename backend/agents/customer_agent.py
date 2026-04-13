import json
import os
from sqlalchemy.orm import Session
import models
from database import set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sua_chave_aqui":
        return None
    return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.1)

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int, base_url: str = ""):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env."}

    # =========================================================================
    # ROBÔ DE RESERVAS UNIFICADO (Smart Booking Engine)
    # =========================================================================
    @tool
    def smart_booking_engine(
        action: str, 
        mode: str = "NORMAL", 
        guest_id: int = None,
        check_in: str = "", 
        check_out: str = "", 
        group_size: int = 1,
        room_id: str = None,
        companions: List[dict] = [],
        check_in_time: str = "14:00",
        check_out_time: str = "14:00"
    ) -> dict:
        """
        Robô unificado para consulta e reserva.
        Ações: 'check' (ver vagas), 'reserve' (criar reserva).
        Modos: 'NORMAL' (família/amigos), 'CARAVANA' (bloqueia pousada toda).
        """
        try:
            if not check_in or not check_out or check_in.strip() == "" or check_out.strip() == "":
                return {"error": "INSTRUÇÃO: Pergunte ao cliente qual data de chegada (check-in) e saída (check-out) ele deseja."}
                
            set_tenant_context(db, tenant_id)
            try:
                ci = datetime.strptime(check_in, "%Y-%m-%d").date()
                co = datetime.strptime(check_out, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "INSTRUÇÃO: Datas inválidas. Peça ao cliente as datas no formato correto ou confirme o período."}

            # 1. Busca Eventos no Período
            event = db.query(models.Event).filter(
                models.Event.start_date <= co,
                models.Event.end_date >= ci
            ).first()

            days = calculate_daily_rates_count(ci, co, check_in_time, check_out_time)
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            
            # --- AÇÃO: CHECK ---
            if action == "check":
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
                            if has_weekend:
                                allowed = False
                    if allowed:
                        final_rooms.append(r)

                return {
                    "available_rooms": [{"id": r.id, "cap": r.max_capacity, "price": r.price_per_night} for r in final_rooms],
                    "event_info": getattr(event, "name", "Nenhum evento") if event else "Nenhum evento",
                    "total_capacity": sum(r.max_capacity for r in final_rooms),
                    "pricing_model": settings.get("pousada_pricing_model", "per_person"),
                    "rules_active": [r.name for r in active_rules]
                }

            # --- AÇÃO: RESERVE ---
            if action == "reserve":
                if not guest_id: return {"error": "guest_id é necessário para reserva."}
                guest = db.query(models.Guest).get(guest_id)
                if not guest: return {"error": "Hóspede não encontrado."}

                total_amount = 0.0
                daily_rate_label = ""
                
                if event and (event.daily_rate_single > 0 or event.daily_rate_couple > 0):
                    adults = 1 + len([c for c in companions if int(c.get('age', 18)) >= 13])
                    children = len([c for c in companions if 7 <= int(c.get('age', 0)) < 13])
                    
                    if adults == 1 and event.daily_rate_single > 0:
                        total_amount = (event.daily_rate_single + (children * event.daily_rate_child)) * days
                        daily_rate_label = f"Tarifa Solteiro Evento: R${event.daily_rate_single}"
                    elif adults >= 2 and event.daily_rate_couple > 0:
                        extras = adults - 2
                        total_amount = (event.daily_rate_couple + (extras * event.daily_rate_extra) + (children * event.daily_rate_child)) * days
                        daily_rate_label = f"Tarifa Casal Evento: R${event.daily_rate_couple}"
                    else:
                        daily_rate = event.daily_rate or 100.0
                        g_age = 18
                        if getattr(guest, "birth_date", None):
                            today = date.today()
                            bd = guest.birth_date
                            g_age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                        ages = [g_age] + [int(c.get('age', 18)) for c in companions]
                        pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
                        total_amount = pricing["total"]
                        daily_rate_label = f"Tarifa Especial Evento: R${daily_rate}/pessoa"
                else:
                    room = db.query(models.Room).get(room_id)
                    daily_rate = room.price_per_night if room else 100.0
                    g_age = 18
                    if getattr(guest, "birth_date", None):
                        today = date.today()
                        bd = guest.birth_date
                        g_age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                    ages = [g_age] + [int(c.get('age', 18)) for c in companions]
                    pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
                    total_amount = pricing["total"]
                    daily_rate_label = f"Tarifa Padrão: R${daily_rate}"

                if mode == "NORMAL":
                    if group_size > 1:
                        if len(companions) < (group_size - 1):
                            return {"error": f"Faltam dados dos acompanhantes. Preciso do nome e idade dos {group_size - 1} extras."}
                        for c in companions:
                            if not c.get("name") or str(c.get("age", "")) == "":
                                return {"error": "Cada acompanhante deve ter nome e idade informados."}
                    
                    final_total = total_amount
                    multiplier_label = ""
                    
                    fds_rule = next((rule for rule in active_rules if rule.name == "Tarifa Fim de Semana"), None)
                    if fds_rule:
                        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                        if has_weekend:
                            mult = float(fds_rule.config.get("multiplier", 1.0))
                            final_total *= mult
                            multiplier_label += f" | Ajuste FDS (x{mult})"

                    long_rule = next((rule for rule in active_rules if rule.name == "Desconto Estadia Longa"), None)
                    if long_rule:
                        min_d = int(long_rule.config.get("min_days", 999))
                        if days >= min_d:
                            disc = float(long_rule.config.get("discount_percent", 0)) / 100.0
                            final_total *= (1 - disc)
                            multiplier_label += f" | Desc. Longa Estadia (-{disc*100}%)"

                    booking = models.Booking(
                        guest_id=guest_id, room_id=room_id, check_in_date=ci, check_out_date=co,
                        check_in_time=check_in_time, check_out_time=check_out_time,
                        total_guests=group_size, daily_rate=0.0, total_amount=final_total, 
                        mode=models.BookingMode.NORMAL, status=models.BookingStatus.PENDENTE,
                        notes=f"{daily_rate_label}{multiplier_label}"
                    )
                    db.add(booking)
                    db.commit()
                    db.refresh(booking)
                    for c in companions:
                        age_val = int(c.get('age', 18)) if str(c.get('age', '')).isdigit() else 18
                        db.add(models.Companion(booking_id=booking.id, name=c['name'], age=age_val))
                    db.commit()
                    return {"success": True, "booking_id": booking.id, "total": final_total, "type": "FAMILIA", "label": f"{daily_rate_label}{multiplier_label}"}

                if mode == "CARAVANA":
                    if not event or event.daily_rate <= 0:
                        return {"error": "Reservas de Caravana exigem um Evento cadastrado com tarifa por pessoa."}
                    
                    occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                        models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                        models.Booking.check_out_date > ci,
                        models.Booking.check_in_date < co
                    ).all()]
                    
                    available_rooms = db.query(models.Room).filter(
                        models.Room.id.notin_(occupied),
                        models.Room.status != models.RoomStatus.MANUTENCAO
                    ).order_by(models.Room.max_capacity.desc()).all()
                    
                    target_rooms = []
                    current_cap = 0
                    for r in available_rooms:
                        target_rooms.append(r)
                        current_cap += r.max_capacity
                        if current_cap >= group_size:
                            break
                    
                    if current_cap < group_size:
                        return {"error": f"Capacidade insuficiente. Apenas {current_cap} vagas disponíveis, mas o grupo é de {group_size}."}

                    total_amount_global = daily_rate * group_size * days
                    amount_per_room = total_amount_global / len(target_rooms) if target_rooms else 0
                    
                    main_booking_id = None
                    for r in target_rooms:
                        b = models.Booking(
                            guest_id=guest_id, room_id=r.id, check_in_date=ci, check_out_date=co,
                            check_in_time=check_in_time, check_out_time=check_out_time,
                            total_guests=group_size, daily_rate=daily_rate, total_amount=amount_per_room,
                            mode=models.BookingMode.CARAVANA, status=models.BookingStatus.PENDENTE,
                            notes=f"Líder da Caravana: {guest.name}. Distribuição Alocada dinamicamente pelo Robô. (Vaga total selecionada: {current_cap})"
                        )
                        db.add(b)
                        db.commit()
                        db.refresh(b)
                        if not main_booking_id: main_booking_id = b.id
                    
                    return {
                        "success": True, 
                        "leader_booking_id": main_booking_id, 
                        "total": total_amount_global, 
                        "rooms_blocked": len(target_rooms), 
                        "total_capacity_reserved": current_cap,
                        "type": "CARAVANA"
                    }

            return {"error": "Ação inválida ou má formulada."}
        except Exception as e:
            db.rollback()
            return {"error": f"Erro técnico no motor de reserva: {str(e)}"}

    # =========================================================================
    # MULTI-TOOLS COMPLEMENTARES
    # =========================================================================
    @tool
    def robot_generate_payment_qr(booking_id: int) -> dict:
        """
        Gera o QR Code PIX IMEDIATAMENTE após criar uma reserva.
        """
        try:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking: return {"error": "Reserva não encontrada."}
            
            from routers.payments import get_tenant_mp_token
            from payments.mercadopago_service import MercadoPagoService
            
            try:
                token = get_tenant_mp_token(db, tenant_id)
                mp = MercadoPagoService()
            except:
                return {"error": "Sistema de pagamento sob manutenção. Tente em instantes."}
                
            metadata = {"booking_id": booking.id, "type": "public", "tenant_id": tenant_id}
            description = f"Pagamento Reserva #{booking.id}"
            
            payer = None
            guest = booking.guest
            if guest:
                from routers.payments import _cpf_digits, _cpf_valid
                cpf = _cpf_digits(guest.document or "")
                cpf = cpf if _cpf_valid(cpf) else "19119119100"
                full = (guest.name or "Hóspede").strip()
                parts = full.split()
                payer = {
                    "email": guest.email or "guest@test.com",
                    "first_name": parts[0] if parts else "Hóspede",
                    "last_name": parts[-1] if len(parts) > 1 else "Visitante",
                    "identification": {"type": "CPF", "number": cpf}
                }
                
            result = mp.create_pix_payment(token, tenant_id, booking.total_amount, description, metadata, payer=payer)
            response = result.get("response") or {}
            poi = (response.get("point_of_interaction") or {}).get("transaction_data") or {}
            qr_base64 = poi.get("qr_code_base64")
            qr_code = poi.get("qr_code")
            
            if not qr_base64: return {"error": "Falha ao gerar QR Code bancário."}
                
            return {
                "success": True,
                "instructions": "Peça o pagamento para confirmar. Exiba o QR Code e o Copia-e-Cola.",
                "qr_code_image_markdown": f"![QR Code PIX](data:image/png;base64,{qr_base64})",
                "copia_e_cola": f"`{qr_code}`"
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro financeiro: {str(e)}"}

    @tool
    def robot_search_events(query: str) -> dict:
        """
        Busca agenda de Eventos/Feriados pelo nome. Use para descobrir datas.
        """
        try:
            set_tenant_context(db, tenant_id)
            events = db.query(models.Event).filter(models.Event.name.ilike(f"%{query}%")).all()
            if not events: return {"error": f"Nenhum evento '{query}' localizado."}
            return {
                "events": [{
                    "name": e.name, "start_date": e.start_date.strftime("%Y-%m-%d"), "end_date": e.end_date.strftime("%Y-%m-%d")
                } for e in events],
                "instructions": "Use essas datas no smart_booking_engine(action='check')."
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro ao buscar evento: {str(e)}"}

    @tool
    def find_guest(cpf: str = "", name: str = "") -> dict:
        """Busca hóspede por CPF ou Nome. Se não achar, emite o link de registro."""
        try:
            set_tenant_context(db, tenant_id)
            if cpf:
                clean_cpf = "".join(filter(str.isdigit, cpf))
                g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
                if g: return {"id": g.id, "name": g.name, "cpf": g.document}
            if name:
                gs = db.query(models.Guest).filter(models.Guest.name.ilike(f"%{name}%")).all()
                if gs: return {"results": [{"id": x.id, "name": x.name} for x in gs]}
            
            prefix = base_url.rstrip("/") if base_url else ""
            link_to_send = f"{prefix}/{tenant_id}/registrar?cpf={clean_cpf if cpf else ''}"
            return {
                "error": "Nenhum hóspede localizado.",
                "registration_instructions": "O cliente não tem cadastro. Envie EXATAMENTE o link abaixo (NUNCA substitua por example.com). Diga para ele preencher e voltar ao chat.",
                "link_intocavel": link_to_send
            }
        except Exception as e:
            db.rollback()
            return {"error": f"Erro ao buscar hóspede: {str(e)}"}

    # =========================================================================
    # CONFIGURAÇÃO DO AGENTE
    # =========================================================================
    tools = [smart_booking_engine, robot_generate_payment_qr, robot_search_events, find_guest]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content="""Você é o Especialista de Reservas da Pousada.
Sua missão é conduzir o hóspede até a reserva de ponta a ponta.

DIRETRIZES DE FLUXO:
1. **IDENTIFICAÇÃO**: Peça sempre o CPF. Use 'find_guest'. Se ele não tiver cadastro, envie o 'link_intocavel'.
2. **DISTINÇÃO DE MODO**:
   - Familiar/Amigos (2-6 pessoas): Mode='NORMAL'. Peça NOME e IDADE de cada companheiro antes de fechar.
   - Caravana/Excursão (+15 pessoas): Mode='CARAVANA'. Peça apenas o total de pessoas e CPF do líder.
3. **EVENTOS**: Se o cliente citar um evento (ex: 'Moto Capital') mas não souber a data, use 'robot_search_events'.
4. **PESQUISA**: Use 'smart_booking_engine'(action='check') para vagas e preços. Informe tarifas de eventos se houver.
5. **RESERVA**: Use 'smart_booking_engine'(action='reserve') para criar o bloqueio.
6. **PAGAMENTO**: Assim que o motor retornar sucesso com um booking_id, use IMEDIATAMENTE 'robot_generate_payment_qr' para exibir o QR Code PIX. Diga que a reserva está PENDENTE até o pagamento.

RESPOSTA FINAL: Seja gentil, use emojis e confirme as regras (descontos, fim de semana) aplicadas.""")

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
    for h in history[-20:]:
        role = h.get("role", "user")
        if role == "user": lc_messages.append(HumanMessage(content=h.get("content", "")))
        elif role == "assistant": lc_messages.append(AIMessage(content=h.get("content", "")))
    lc_messages.append(HumanMessage(content=message))

    try:
        final_state = await app.ainvoke({"messages": lc_messages})
        return {"response": final_state["messages"][-1].content}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"response": "Erro ao processar sua solicitação no motor de reserva inteligente."}
