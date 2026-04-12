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

async def handle_customer_query(message: str, history: list, db: Session, tenant_id: int):
    llm = get_llm()
    if not llm:
        return {"response": "A chave da OpenAI não foi configurada. Por favor, adicione sua API Key no arquivo .env."}

    # =========================================================================
    # ROBÔ DE RESERVAS (Smart Booking Engine)
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
            set_tenant_context(db, tenant_id)
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
        except:
            return {"error": "Datas obrigatórias no formato YYYY-MM-DD."}

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
            
            # Aplicação de Restrições nas Salas Disponíveis
            final_rooms = []
            for r in rooms:
                allowed = True
                # Regra: Restrição de Casal
                couple_rule = next((rule for rule in active_rules if rule.name == "Restrição de Casal"), None)
                if couple_rule and group_size == 2:
                    restricted_rooms = [rid.strip() for rid in couple_rule.config.get("room_ids", "").split(",") if rid.strip()]
                    if r.id in restricted_rooms:
                        # Verifica se há final de semana no período
                        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                        if has_weekend:
                            allowed = False
                
                if allowed:
                    final_rooms.append(r)

            return {
                "available_rooms": [{"id": r.id, "cap": r.max_capacity, "price": base_rate or r.price_per_night} for r in final_rooms],
                "event_info": msg,
                "total_capacity": sum(r.max_capacity for r in final_rooms),
                "pricing_model": settings.get("pousada_pricing_model", "per_person"),
                "rules_active": [r.name for r in active_rules]
            }

        # --- AÇÃO: RESERVE ---
        if action == "reserve":
            if not guest_id: return {"error": "guest_id é necessário para reserva."}
            guest = db.query(models.Guest).get(guest_id)
            if not guest: return {"error": "Hóspede não encontrado."}

            # RESOLUÇÃO DE VALORES (Tabela de Evento vs Padrao)
            total_amount = 0.0
            daily_rate_label = ""
            
            if event and (event.daily_rate_single > 0 or event.daily_rate_couple > 0):
                # Lógica de Tarifação de Evento
                adults = 1 + len([c for c in companions if c.get('age', 18) >= 13])
                children = len([c for c in companions if c.get('age', 0) < 13 and c.get('age', 0) >= 7])
                
                if adults == 1 and event.daily_rate_single > 0:
                    total_amount = (event.daily_rate_single + (children * event.daily_rate_child)) * days
                    daily_rate_label = f"Tarifa Solteiro Evento: R${event.daily_rate_single}"
                elif adults >= 2 and event.daily_rate_couple > 0:
                    extras = adults - 2
                    total_amount = (event.daily_rate_couple + (extras * event.daily_rate_extra) + (children * event.daily_rate_child)) * days
                    daily_rate_label = f"Tarifa Casal Evento: R${event.daily_rate_couple}"
                else:
                    # Fallback para diária por pessoa se não houver lógica de casal/solteiro
                    daily_rate = event.daily_rate or 100.0
                    ages = [guest.age or 18] + [int(c['age']) for c in companions]
                    pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
                    total_amount = pricing["total"]
                    daily_rate_label = f"Tarifa Especial Evento: R${daily_rate}/pessoa"
            else:
                # Tarifas Padrão da Pousada
                room = db.query(models.Room).get(room_id)
                daily_rate = room.price_per_night if room else 100.0
                ages = [guest.age or 18] + [int(c['age']) for c in companions]
                pricing = calculate_reservation_total(daily_rate, days, ages, settings=settings)
                total_amount = pricing["total"]
                daily_rate_label = f"Tarifa Padrão: R${daily_rate}"

            # VALIDAÇÃO DE CONTEXTO (NORMAL)
            if mode == "NORMAL":
                if group_size > 1:
                    # Verifica se todos os acompanhantes têm nome e idade
                    if len(companions) < (group_size - 1):
                        return {"error": f"Faltam dados dos acompanhantes. Preciso do nome e idade dos {group_size - 1} extras."}
                    for c in companions:
                        if not c.get("name") or not c.get("age"):
                            return {"error": "Cada acompanhante deve ter nome e idade informados."}
                
                # --- APLICAR REGRAS DE NEGÓCIO AO TOTAL ---
                final_total = total_amount
                multiplier_label = ""
                
                # 1. Multiplicador de Fim de Semana
                fds_rule = next((rule for rule in active_rules if rule.name == "Tarifa Fim de Semana"), None)
                if fds_rule:
                    has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                    if has_weekend:
                        mult = float(fds_rule.config.get("multiplier", 1.0))
                        final_total *= mult
                        multiplier_label += f" | Ajuste FDS (x{mult})"

                # 2. Desconto Estadia Longa
                long_rule = next((rule for rule in active_rules if rule.name == "Desconto Estadia Longa"), None)
                if long_rule:
                    min_d = int(long_rule.config.get("min_days", 999))
                    if days >= min_d:
                        disc = float(long_rule.config.get("discount_percent", 0)) / 100.0
                        final_total *= (1 - disc)
                        multiplier_label += f" | Desc. Longa Estadia (-{disc*100}%)"

                # Criar 1 reserva
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
                    db.add(models.Companion(booking_id=booking.id, name=c['name'], age=int(c['age'])))
                db.commit()
                return {"success": True, "booking_id": booking.id, "total": final_total, "type": "FAMILIA", "label": f"{daily_rate_label}{multiplier_label}"}

            # VALIDAÇÃO DE CONTEXTO (CARAVANA)
            if mode == "CARAVANA":
                if not event or event.daily_rate <= 0:
                    return {"error": "Reservas de Caravana exigem um Evento cadastrado com tarifa por pessoa."}
                
                # Seleciona quartos disponíveis o suficiente para cobrir a capacidade
                occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                    models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                    models.Booking.check_out_date > ci,
                    models.Booking.check_in_date < co
                ).all()]
                
                # Busca quartos não ocupados, priorizando os de maior capacidade
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
                        notes=f"Líder da Caravana: {guest.name}. Grupo de {group_size} pessoas. (Vaga total selecionada: {current_cap})"
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

        return {"error": "Ação inválida."}

    # Mantemos ferramentas de busca para o fluxo de identificação
    @tool
    def find_guest(cpf: str = "", name: str = "") -> dict:
        """Busca hóspede por CPF ou Nome."""
        if cpf:
            clean_cpf = "".join(filter(str.isdigit, cpf))
            g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if g: return {"id": g.id, "name": g.name, "cpf": g.document}
        if name:
            gs = db.query(models.Guest).filter(models.Guest.name.ilike(f"%{name}%")).all()
            return {"results": [{"id": x.id, "name": x.name} for x in gs]}
        return {"error": "Nenhum dado informado."}

    tools = [smart_booking_engine, find_guest]
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content="""Você é o Especialista de Reservas da Pousada.
Sua missão é conduzir o hóspede até a reserva, garantindo a coleta correta de dados.

DIRETRIZES DE COLETA:
1. **IDENTIFICAÇÃO**: Peça sempre o CPF primeiro. Use 'find_guest'.
2. **DISTINÇÃO DE MODO**:
   - Se o grupo for Familiar (2-6 pessoas): Você DEVE obrigatoriamente pedir NOME e IDADE de cada companheiro antes de reservar. Não pule isso!
   - Se o usuário falar em 'Caravana', 'Excursão' ou 'Grupo Grande': Use mode='CARAVANA'. Avise que a pousada toda será bloqueada para eles. Peça apenas o total de pessoas.
3. **EVENTOS**: O robô de reserva já detecta eventos por data. Se encontrar um evento, informe a tarifa especial dele.
4. **CÁLCULO**: O robô faz os cálculos. Apenas reporte o valor final.
5. **RESPOSTA**: Seja gentil, use emojis e apresente um resumo claro antes de confirmar a reserva.

Lembre-se: Para Caravanas, não precisamos de nomes individuais, apenas do líder. Para Famílias, nomes e idades são obrigatórios para o preço estar certo.
Sempre informe o hóspede caso alguma Regra de Negócio (como multiplicador de fim de semana ou desconto por longa estadia) seja aplicada ao valor final.""")

    def call_model(state: MessagesState):
        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", lambda s: "tools" if s["messages"][-1].tool_calls else END)
    workflow.add_edge("tools", "agent")
    app = workflow.compile()

    # History Transformation
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
        import traceback
        traceback.print_exc()
        return {"response": "Erro ao processar reserva inteligente."}
