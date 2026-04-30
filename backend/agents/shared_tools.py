import os
import json
import models
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import Session
from database import SessionLocal, set_tenant_context
from agents.state_manager import StateManager
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List, Any
from utils.payment_helpers import prepare_payer_data, process_mp_response, _cpf_valid
import logging

logger = logging.getLogger(__name__)

# --- UTILS DE DATA (UNIVERSAL) ---
def universal_date_parser(date_val):
    """Interpreta datas em formato DD/MM, DD/MM/YYYY ou YYYY-MM-DD. Aceita date/datetime nativo."""
    if not date_val: return None
    
    # Camada 1: Robustez de Tipos (Mente Central)
    if isinstance(date_val, (date, datetime)):
        return date_val.date() if isinstance(date_val, datetime) else date_val

    date_str = str(date_val).strip()
    now = datetime.now()
    try:
        if "/" in date_str:
            parts = date_str.split("/")
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else now.year
            target_date = date(year, month, day)
            if len(parts) <= 2 and target_date < now.date():
                target_date = date(year + 1, month, day)
            return target_date
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return None

# --- MOTOR DE CÁLCULO ---
def calculate_booking_quote(db, tenant_id, room_id, check_in_date, check_out_date, group_size, ages: List[int] = []):
    """Fonte única de verdade para cálculos de reserva."""
    set_tenant_context(db, tenant_id)
    ci = check_in_date
    co = check_out_date
    
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
    
    # Busca horários da política
    policy_ci = settings.get("check_in_time", "14:00")
    policy_co = settings.get("check_out_time", "12:00")
    
    days = calculate_daily_rates_count(ci, co, policy_check_in_time=policy_ci, policy_check_out_time=policy_co)
    active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
    room = db.query(models.Room).get(room_id)
    daily_base = room.price_per_night if room else 100.0

    event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()
    total_amount = 0.0
    note_parts = []
    
    full_ages = ages[:group_size]
    if len(full_ages) < group_size:
        full_ages += [18] * (group_size - len(full_ages))

    if event and (event.daily_rate_single > 0 or event.daily_rate_couple > 0):
        # Usa faixas etárias dinâmicas para o cálculo de evento também
        age_child = int(settings.get('age_child_until', 12))
        age_infant = int(settings.get('age_infant_until', 6))
        
        adults = len([age for age in full_ages if age > age_child])
        children = len([age for age in full_ages if age_infant < age <= age_child])
        
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

    # Regras Extras (FDS, Descontos)
    fds_rule = next((r for r in active_rules if r.name == "Tarifa Fim de Semana"), None)
    if fds_rule:
        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
        if has_weekend:
            mult = float(fds_rule.config.get("multiplier", 1.2))
            total_amount *= mult
            note_parts.append(f"Ajuste FDS (x{mult})")

    return {"total": total_amount, "days": days, "notes": " | ".join(note_parts), "event_name": event.name if event else None}

# --- LOGICAS ATOMICAS ---
def find_guest_logic(tenant_id: int, cpf: str = "", name: str = "", base_url: str = "", session_id: str = None) -> dict:
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        clean_cpf = "".join(filter(str.isdigit, cpf)) if cpf else ""
        if clean_cpf:
            g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if g: 
                return {
                    "found": True, 
                    "id": g.id, 
                    "name": g.name, 
                    "cpf": g.document, 
                    "age": g.age
                }
        
        prefix = base_url.rstrip("/") if base_url else ""
        sid_param = f"&sid={session_id}" if session_id else ""
        link = f"{prefix}/{tenant_id}/registrar?cpf={clean_cpf}{sid_param}"
        return {
            "found": False, 
            "error": "Hóspede não encontrado.", 
            "registration_link": link
        }

def availability_check_logic(tenant_id: int, check_in: str, check_out: str, group_size: int = 1, ages: List[int] = []) -> dict:
    try:
        if not check_in or not check_out: return {"error": "Por favor, me informe as datas de chegada e saída!"}
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            now = datetime.now()
            ci = universal_date_parser(check_in)
            co = universal_date_parser(check_out)
            if not ci or not co: return {"error": "Data inválida."}
            if ci < now.date(): return {"error": "Data no passado."}

            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
            policy_ci = settings.get("check_in_time", "14:00")
            policy_co = settings.get("check_out_time", "12:00")
            days = calculate_daily_rates_count(ci, co, policy_check_in_time=policy_ci, policy_check_out_time=policy_co)
            
            # Bloqueio de Overbooking: Considera CONFIRMADO, ATIVO e PENDENTE (se não expirado)
            expiration_limit = datetime.now() - timedelta(hours=2)
            
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.check_out_date > ci, 
                models.Booking.check_in_date < co,
                (
                    models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]) |
                    ((models.Booking.status == models.BookingStatus.PENDENTE) & (models.Booking.created_at >= expiration_limit))
                )
            ).all()]
            rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()
            
            # 1. Busca por Quartos Individuais (Solução Direta)
            final_rooms = []
            pricing_model = settings.get('pousada_pricing_model', 'per_person')
            suffix = "/pessoa" if pricing_model == "per_person" else "/quarto"
            
            for r in rooms:
                if r.max_capacity >= group_size:
                    quote = calculate_booking_quote(db, tenant_id, r.id, ci, co, group_size, ages)
                    final_rooms.append({
                        "room_number": r.id, 
                        "type": r.type or "Quarto", 
                        "capacity": r.max_capacity,
                        "total_quote": quote["total"], 
                        "pricing_description": f"R$ {quote['total']:.2f} total ({quote['days']} diárias {suffix})",
                        "notes": quote["notes"]
                    })

            # 2. Busca por Combinações (Smart Split) - Inteligência Proativa
            suggested_splits = []
            if group_size > 1:
                def find_combo(sorted_list):
                    combo = []
                    cap = 0
                    for r in sorted_list:
                        combo.append(r)
                        cap += r.max_capacity
                        if cap >= group_size:
                            total = 0
                            details = []
                            for cr in combo:
                                q = calculate_booking_quote(db, tenant_id, cr.id, ci, co, cr.max_capacity if cr.max_capacity < group_size else group_size)
                                total += q["total"]
                                details.append(f"{cr.type} #{cr.id}")
                            return {
                                "rooms": [cr.id for cr in combo],
                                "description": " + ".join(details),
                                "total_price": total,
                                "pricing_description": f"R$ {total:.2f} total",
                                "room_count": len(combo)
                            }
                    return None

                # ESTRATÉGIA A: CONFORTO (Menos quartos, maior capacidade primeiro)
                sorted_cap = sorted(rooms, key=lambda x: x.max_capacity, reverse=True)
                comfort = find_combo(sorted_cap)
                if comfort:
                    comfort["strategy"] = "conforto"
                    comfort["message"] = f"Opção Conforto ({comfort['room_count']} quartos): {comfort['description']} por R$ {comfort['total_price']:.2f}"
                    suggested_splits.append(comfort)

                # ESTRATÉGIA B: ECONOMIA (Menor preço primeiro)
                sorted_price = sorted(rooms, key=lambda x: (x.price_per_night, -x.max_capacity))
                economy = find_combo(sorted_price)
                if economy and (not comfort or economy["total_price"] < comfort["total_price"] or economy["room_count"] != comfort["room_count"]):
                    economy["strategy"] = "economia"
                    economy["message"] = f"Opção Econômica ({economy['room_count']} quartos): {economy['description']} por R$ {economy['total_price']:.2f}"
                    suggested_splits.append(economy)

            return {
                "available": len(rooms) > 0,
                "rooms": final_rooms[:5], 
                "combinations": suggested_splits,
                "pricing_model": pricing_model,
                "summary": f"Encontrei {len(final_rooms)} opções de quartos individuais e {len(suggested_splits)} combinações inteligentes."
            }
    except Exception as e:
        return {"error": str(e)}

def unified_booking_flow(tenant_id: int, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List = [], mode: str = "NORMAL") -> dict:
    normalized_companions = []
    for c in companions:
        if isinstance(c, str): normalized_companions.append({"name": c, "age": 18})
        elif isinstance(c, dict): normalized_companions.append(c)
    
    res_booking = booking_creation_logic(tenant_id, guest_id, room_id, check_in, check_out, group_size, normalized_companions, mode)
    if "error" in res_booking: return res_booking
    res_payment = payment_info_logic(tenant_id, res_booking["booking_id"])
    return {"success": True, "booking_details": res_booking, "payment_details": res_payment}

def booking_creation_logic(tenant_id: int, guest_id: int, room_id: Any, check_in: str, check_out: str, group_size: int, companions: List[dict] = [], mode: str = "NORMAL") -> dict:
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            ci = universal_date_parser(check_in)
            co = universal_date_parser(check_out)
            guest = db.get(models.Guest, guest_id)
            if not guest:
                return {"error": "Hóspede principal não identificado. Por favor, forneça seu CPF primeiro."}
            
            # Normalizar room_id para lista (suporte a multi-quarto)
            room_ids = [room_id] if isinstance(room_id, (str, int)) else list(room_id)
            
            # --- VALIDAÇÃO ATÔMICA DE OVERBOOKING ---
            expiration_limit = datetime.now() - timedelta(hours=2)
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.room_id.in_(room_ids),
                models.Booking.check_out_date > ci, 
                models.Booking.check_in_date < co,
                (
                    models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]) |
                    ((models.Booking.status == models.BookingStatus.PENDENTE) & (models.Booking.created_at >= expiration_limit))
                )
            ).all()]
            
            if occupied:
                return {"error": f"Sinto muito, o quarto {occupied[0]} acabou de ser reservado por outra pessoa para estas datas."}
            # ----------------------------------------

            ages = [guest.age or 18] + [int(c.get('age', 18)) for c in companions]
            
            # Cálculo de preço consolidado para todos os quartos
            total_amount = 0.0
            notes_list = []
            
            # Distribuir pessoas entre os quartos para o cálculo (aproximado)
            avg_people = group_size // len(room_ids)
            remainder = group_size % len(room_ids)
            
            for i, r_id in enumerate(room_ids):
                p_count = avg_people + (1 if i < remainder else 0)
                q = calculate_booking_quote(db, tenant_id, r_id, ci, co, p_count, ages)
                total_amount += q["total"]
                notes_list.append(f"Quarto {r_id}: {q['notes']}")

            booking = models.Booking(
                tenant_id=tenant_id,
                guest_id=guest_id, 
                room_id=room_ids[0], 
                check_in_date=ci, 
                check_out_date=co,
                total_guests=group_size, 
                total_amount=total_amount, 
                status=models.BookingStatus.PENDENTE, 
                notes=" | ".join(notes_list)
            )
            db.add(booking)
            db.flush() # Gerar ID do booking para os filhos
            
            # Registrar todos os quartos
            for r_id in room_ids:
                db.add(models.BookingRoom(booking_id=booking.id, room_id=r_id))
            
            # Registrar acompanhantes com tenant_id explícito
            for c in companions:
                db.add(models.Companion(
                    tenant_id=tenant_id,
                    booking_id=booking.id, 
                    name=c.get('name', 'N/A'), 
                    age=int(c.get('age', 18))
                ))
            
            db.commit()
            return {"success": True, "booking_id": booking.id, "total": total_amount}
    except Exception as e:
        return {"error": str(e)}

def payment_info_logic(tenant_id: int, booking_id: int) -> dict:
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            if not booking:
                return {"error": f"Reserva #{booking_id} não encontrada."}
            
            # 1. TENTA TOKEN DO MERCADO PAGO (PRIORIDADE)
            config = db.query(models.TenantConfig).filter(
                models.TenantConfig.tenant_id == tenant_id,
                models.TenantConfig.is_active == True
            ).first()
            print(f"[PAYMENT_DEBUG] Tenant ID: {tenant_id}")
            print(f"[PAYMENT_DEBUG] Config found: {config.id if config else 'None'}")
            manual_key = config.manual_pix_key if config else None
            print(f"[PAYMENT_DEBUG] Initial manual_key: {manual_key}")
            qr_data = None
            
            try:
                from payments.mercadopago_service import MercadoPagoService
                from routers.payments import get_tenant_mp_token
                token = get_tenant_mp_token(db, tenant_id)
                if token:
                    mp = MercadoPagoService()
                    payer = prepare_payer_data(booking.guest)
                    res = mp.create_pix_payment(
                        token, tenant_id, booking.total_amount,
                        f"Reserva #{booking.id}", {"booking_id": booking.id}, payer=payer
                    )
                    payment_result = process_mp_response(res)
                    if payment_result.get("qr_code"):
                        qr_data = {
                            "image": payment_result.get("qr_code_base64"),
                            "code": payment_result.get("qr_code"),
                            "link": payment_result.get("payment_url")
                        }
            except Exception as mp_err:
                print(f"[PAYMENT_LOG] Mercado Pago indisponível: {mp_err}")
            
            # 2. FALLBACK: Se MP falhou, busca chave PIX cadastrada nas configurações do sistema
            if not qr_data:
                # Prioridade: config do tenant > setting global
                global_pix = db.query(models.SystemSetting).filter(
                    models.SystemSetting.key == "pousada_pix_key",
                    models.SystemSetting.tenant_id == tenant_id
                ).first()
                print(f"[PAYMENT_DEBUG] Global PIX found: {global_pix.value if global_pix else 'None'}")
                manual_key = manual_key or (global_pix.value if global_pix else None)
                print(f"[PAYMENT_DEBUG] Final manual_key: {manual_key}")
            
            # 3. Define o método de pagamento de forma explícita para o agente
            if qr_data:
                payment_method = "mercadopago"
            elif manual_key:
                payment_method = "pix_manual"
            else:
                payment_method = "nenhum"
            
            return {
                "booking_id": booking_id,
                "total": booking.total_amount,
                "pix_qr": qr_data,
                "manual_key": manual_key,
                "payment_method": payment_method  # Campo explícito para o agente não adivinhar
            }
    except Exception as e:
        return {"error": str(e)}

def confirm_payment_logic(tenant_id: int, booking_id: int, method: str = "pix") -> dict:
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            booking.status = models.BookingStatus.CONFIRMADO
            booking.payment_status = models.PaymentStatus.PAGO
            rev = models.Revenue(description=f"Pagamento Reserva #{booking.id}", amount=booking.total_amount, category=models.RevenueCategory.HOSPEDAGEM, payment_method=method.lower(), booking_id=booking.id, created_at=datetime.now())
            db.add(rev)
            db.commit()
            return {"success": True}
    except Exception as e:
        return {"error": str(e)}

def find_booking_logic(tenant_id: int, cpf: str = "", name: str = "", room_id: str = "", booking_id: int = None) -> dict:
    """Busca reservas ativas ou recentes por ID, CPF, Nome ou Quarto."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        query = db.query(models.Booking).join(models.Guest)
        
        if booking_id:
            query = query.filter(models.Booking.id == booking_id)
        elif cpf:
            clean_cpf = "".join(filter(str.isdigit, cpf))
            query = query.filter(models.Guest.document == clean_cpf)
        elif name:
            query = query.filter(models.Guest.name.ilike(f"%{name}%"))
        elif room_id:
            query = query.filter(models.Booking.room_id == room_id)
            
        bookings = query.order_by(models.Booking.id.desc()).limit(5).all()
        
        if not bookings:
            return {"error": "Nenhuma reserva encontrada com esses dados."}
            
        results = []
        for b in bookings:
            results.append({
                "id": b.id,
                "hospede": b.guest.name,
                "quarto": b.room_id,
                "status": b.status,
                "check_in": str(b.check_in_date),
                "check_out": str(b.check_out_date),
                "total": b.total_amount
            })
            
        return {"count": len(results), "bookings": results}

def get_combined_business_context(tenant_id: int) -> str:
    """Gera um manual completo de regras de negócio para a IA."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # 1. Configurações de Logística e Políticas
        settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
        
        ci_time = settings.get("check_in_time", "14:00")
        co_time = settings.get("check_out_time", "12:00")
        age_infant = settings.get("age_infant_until", "6")
        age_child = settings.get("age_child_until", "12")
        deposit = settings.get("pousada_deposit_percentage", "100")
        house_rules = settings.get("house_rules_description", "Não informado.")
        
        # 2. Regras de Negócio Ativas (Descontos, etc.)
        active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()
        rules_text = ""
        for r in active_rules:
            rules_text += f"- {r.name}: {r.description}\n"
        
        # 3. Montagem do Manual
        manual = f"""
MANUAL DE REGRAS DA POUSADA (Siga rigorosamente):
- HORÁRIOS: Check-in a partir das {ci_time}. Check-out até as {co_time}.
- POLÍTICA DE IDADES: Bebês até {age_infant} anos. Crianças até {age_child} anos (acima disso é adulto).
- PAGAMENTO: Exigimos {deposit}% de sinal para confirmar a reserva.
- REGRAS DA CASA E CANCELAMENTO: {house_rules}

REGRAS ADICIONAIS ATIVAS:
{rules_text if rules_text else "- Nenhuma regra adicional ativa no momento."}

MEMÓRIA OPERACIONAL E FATOS:
{get_operational_memory_logic(tenant_id)}
"""
        return manual

def get_operational_memory_logic(tenant_id: int, guest_id: int = None) -> str:
    """Recupera fatos e regras da memória operacional do tenant/hóspede."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        query = db.query(models.TenantMemory).filter(models.TenantMemory.is_active == True)
        if guest_id:
            query = query.filter((models.TenantMemory.guest_id == guest_id) | (models.TenantMemory.guest_id == None))
        else:
            query = query.filter(models.TenantMemory.guest_id == None)
        
        mems = query.order_by(models.TenantMemory.importance.desc()).limit(10).all()
        if not mems: return ""
        
        context = "FATOS E REGRAS CONHECIDAS:\n"
        for m in mems:
            context += f"- {m.content} (cat: {m.category})\n"
        return context

def store_operational_memory_logic(tenant_id: int, content: str, category: str = "geral", guest_id: int = None, importance: int = 1) -> dict:
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        new_mem = models.TenantMemory(tenant_id=tenant_id, guest_id=guest_id, category=category, content=content, importance=importance)
        db.add(new_mem)
        db.commit()
        return {"success": True}

def search_events_logic(tenant_id: int, query: str) -> dict:
    """Busca eventos cadastrados por nome."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        events = db.query(models.Event).filter(models.Event.name.ilike(f"%{query}%")).all()
        if not events:
            return {"error": f"Nenhum evento encontrado para '{query}'."}
        
        results = []
        for e in events:
            results.append({
                "name": e.name,
                "start_date": str(e.start_date),
                "end_date": str(e.end_date),
                "description": e.description
            })
        return {"results": results}

def event_listing_logic(tenant_id: int, month: int = None, year: int = None) -> dict:
    """Lista eventos do calendário filtrados por mês e ano."""
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        query = db.query(models.Event)
        
        now = datetime.now()
        target_year = year or now.year
        
        if month:
            import calendar
            _, last_day = calendar.monthrange(target_year, month)
            start_date = date(target_year, month, 1)
            end_date = date(target_year, month, last_day)
            query = query.filter(models.Event.start_date >= start_date, models.Event.start_date <= end_date)
        else:
            # Se não passar mês, pega os próximos 30 dias
            query = query.filter(models.Event.start_date >= now.date(), models.Event.start_date <= now.date() + timedelta(days=30))
            
        events = query.order_by(models.Event.start_date.asc()).all()
        
        if not events:
            return {"error": "Nenhum evento encontrado para o período solicitado."}
            
        return {
            "month": month,
            "year": target_year,
            "events": [{"name": e.name, "start": str(e.start_date), "end": str(e.end_date), "location": e.location} for e in events]
        }

# ============================================================================
# FERRAMENTAS NOVAS (PARTE 5.0)
# ============================================================================

def validate_cpf_real(cpf: str) -> dict:
    """
    Valida CPF usando algoritmo real (Módulo 11).
    
    Parâmetros:
    - cpf: CPF em qualquer formato (123.456.789-00 ou 12345678900)
    
    Retorno:
    {
        'valid': True/False,
        'cpf': str (limpo, 11 dígitos),
        'message': str
    }
    """
    clean_cpf = "".join(filter(str.isdigit, cpf))
    
    if len(clean_cpf) != 11:
        return {
            'valid': False,
            'cpf': None,
            'message': 'CPF deve ter 11 dígitos'
        }
    
    # Usar função real de validação (importada no topo)
    if not _cpf_valid(clean_cpf):
        return {
            'valid': False,
            'cpf': None,
            'message': 'CPF inválido (falhou na validação de dígitos)'
        }
    
    return {
        'valid': True,
        'cpf': clean_cpf,
        'message': 'CPF válido'
    }


def preview_booking_price(
    tenant_id: int,
    room_id: str,
    check_in: str,
    check_out: str,
    group_size: int,
    ages: list = None
) -> dict:
    """
    Calcula preço de forma PREVIEW (sem criar reserva).
    
    Retorno:
    {
        'total': float,
        'days': int,
        'notes': str,
        'event_name': str,
        'pricing_model': str
    }
    """
    try:
        if ages is None:
            ages = []
        
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            
            # Converter datas se forem strings
            ci = check_in if isinstance(check_in, date) else universal_date_parser(check_in)
            co = check_out if isinstance(check_out, date) else universal_date_parser(check_out)
            
            quote = calculate_booking_quote(
                db,
                tenant_id,
                room_id,
                ci,
                co,
                group_size,
                ages
            )
            
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            pricing_model = settings.get('pousada_pricing_model', 'per_person')
            quote['pricing_model'] = pricing_model
            
            return quote
    
    except Exception as e:
        return {'error': f'Erro ao calcular preço: {str(e)}'}


def format_booking_summary(tenant_id: int, session_context: dict) -> dict:
    """
    Formata resumo de reserva para apresentação clara ao hóspede.
    """
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            
            guest_name = session_context.get('guest_name', 'Não informado')
            check_in = session_context.get('check_in')
            check_out = session_context.get('check_out')
            room_id = session_context.get('room_id')
            group_size = session_context.get('group_size', 1)
            companions = session_context.get('companions', [])
            total_price = session_context.get('total_price', 0)
            
            room_ids = [room_id] if isinstance(room_id, (str, int)) else list(room_id)
            rooms = db.query(models.Room).filter(models.Room.id.in_(room_ids)).all()
            
            if rooms:
                room_type = rooms[0].type if len(rooms) == 1 else "Múltiplos Quartos"
                room_display = ", ".join([f"{r.type} #{r.id}" for r in rooms])
            else:
                room_type = "Quarto"
                room_display = ", ".join(map(str, room_ids))
            
            companions_text = ""
            if companions:
                companions_text = "\n**Acompanhantes:**\n"
                for i, c in enumerate(companions, 1):
                    age_str = f", {c.get('age')} anos" if c.get('age') else ""
                    companions_text += f"  {i}. {c.get('name', 'N/A')}{age_str}\n"
            
            summary_text = f"""
╔════════════════════════════════════════════════════════════╗
║           RESUMO DA SUA RESERVA                            ║
╚════════════════════════════════════════════════════════════╝

**Hóspede Principal:** {guest_name}

**Quarto:** {room_type} ({room_display})

**Período:**
  • Check-in: {check_in}
  • Check-out: {check_out}

**Grupo:**
  • Total de pessoas: {group_size} (1 principal + {group_size - 1} acompanhante(s))
{companions_text}

**Valor Total:** R$ {float(total_price):.2f}

╔════════════════════════════════════════════════════════════╗
║  As informações acima estão corretas?                     ║
║  Responda: "Sim" para confirmar ou "Não" para corrigir    ║
╚════════════════════════════════════════════════════════════╝
"""
            
            return {
                'summary_text': summary_text,
                'total': total_price,
                'breakdown': {
                    'guest_name': guest_name,
                    'room_type': room_type,
                    'check_in': str(check_in),
                    'check_out': str(check_out),
                    'group_size': group_size,
                    'total_price': total_price
                }
            }
    
    except Exception as e:
        return {'error': f'Erro ao formatar resumo: {str(e)}'}


def reissue_payment_qr(tenant_id: int, booking_id: int) -> dict:
    """Regenera QR Code PIX para uma reserva existente."""
    return payment_info_logic(tenant_id, booking_id)


def handle_guest_registration_webhook(
    tenant_id: int,
    cpf: str,
    session_id: str = None
) -> dict:
    """Processa webhook quando hóspede se cadastra no formulário público."""
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            clean_cpf = "".join(filter(str.isdigit, cpf))
            
            guest = db.query(models.Guest).filter(
                models.Guest.document == clean_cpf,
                models.Guest.tenant_id == tenant_id
            ).first()
            
            if not guest:
                return {'success': False, 'error': f'Hóspede {clean_cpf} não encontrado', 'webhook_received': False}
            
            if session_id:
                state_manager = StateManager(tenant_id)
                session_data = state_manager.load_session(session_id)
                if session_data:
                    context = session_data.get('context', {})
                    context['guest_id'] = guest.id
                    context['guest_name'] = guest.name
                    context['webhook_received'] = True
                    context['webhook_received_at'] = datetime.utcnow().isoformat()
                    state_manager.update_state(session_id, context) 
            
            return {'success': True, 'guest_id': guest.id, 'guest_name': guest.name, 'webhook_received': True}
    except Exception as e:
        return {'success': False, 'error': str(e), 'webhook_received': False}

def update_booking_status(
    tenant_id: int,
    booking_id: int,
    payment_status: str = None,
    booking_status: str = None,
    payment_id_mp: int = None
) -> dict:
    """
    Atualiza status de pagamento e/ou status da reserva.
    """
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.get(models.Booking, booking_id)
            if not booking:
                return {'error': f'Reserva #{booking_id} não encontrada'}
            
            if payment_status:
                booking.payment_status = payment_status
            
            if booking_status:
                booking.status = booking_status
            
            if payment_id_mp:
                booking.payment_id_mp = payment_id_mp
            
            booking.updated_at = datetime.utcnow()
            db.commit()
            return {'success': True, 'message': f'Reserva #{booking_id} atualizada'}
    except Exception as e:
        return {'error': str(e)}

async def execute_business_logic(tenant_id: int, message: str, context: dict, session_id: str = None) -> dict:
    """
    MOTOR DETERMINÍSTICO (80% Código): 
    Executa a lógica de negócio baseada no estado atual, sem depender da decisão da IA.
    """
    results = {}
    updated_context = context.copy()
    msg_lower = message.lower()
    
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # 1. LOGICA DE BUSCA DE HÓSPEDE (Prioridade Macro)
        cpf_to_search = context.get("cpf")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5174")
        guest_lookup = find_guest_logic(tenant_id, cpf=cpf_to_search, base_url=frontend_url, session_id=session_id)
        results["guest"] = guest_lookup
        if guest_lookup.get("found"):
            updated_context["guest_id"] = guest_lookup["id"]
            updated_context["guest_name"] = guest_lookup["name"]

        # 2. LOGICA DE DISPONIBILIDADE
        if context.get("check_in") and context.get("check_out"):
            availability = availability_check_logic(
                tenant_id, 
                context["check_in"], 
                context["check_out"], 
                context.get("group_size", 1)
            )
            results["availability"] = availability

        # 3. LOGICA DE COTAÇÃO (DETERMINÍSTICA)
        current_quote = None
        if context.get("room_id") and context.get("check_in") and context.get("check_out"):
            room_id = context["room_id"]
            room_ids = [room_id] if isinstance(room_id, (str, int)) else list(room_id)
            
            total_price = 0
            for r_id in room_ids:
                quote = calculate_booking_quote(
                    db, tenant_id, r_id, 
                    universal_date_parser(context["check_in"]), 
                    universal_date_parser(context["check_out"]), 
                    context.get("group_size", 1)
                )
                total_price += quote["total"]
            
            updated_context["total_price"] = total_price
            current_quote = {"total": total_price, "rooms": room_ids}
            results["quote"] = current_quote

        # 4. GATILHO DE PERSISTÊNCIA (80/20 Persistence Rule)
        # Se estamos em CONFIRMATION e o usuário disse SIM, criamos a reserva no banco
        is_confirmation_state = (context.get("current_state") == "CONFIRMATION")
        user_confirmed = any(ok in msg_lower for ok in ["sim", "pode", "ok", "confirmar", "confirmo", "bora", "estão corretas"])
        
        has_essential_data = all([
            updated_context.get("guest_id"),
            updated_context.get("room_id"),
            updated_context.get("check_in"),
            updated_context.get("check_out")
        ])

        if is_confirmation_state and user_confirmed and has_essential_data and not context.get("booking_id"):
            logger.info(f"[LOGIC_PERSISTENCE] Criando reserva para guest {updated_context['guest_id']} no tenant {tenant_id}")
            res_booking = booking_creation_logic(
                tenant_id=tenant_id,
                guest_id=updated_context["guest_id"],
                room_id=updated_context["room_id"],
                check_in=updated_context["check_in"],
                check_out=updated_context["check_out"],
                group_size=updated_context.get("group_size", 1),
                companions=updated_context.get("companions", [])
            )
            if res_booking.get("success"):
                bid = res_booking["booking_id"]
                updated_context["booking_id"] = bid
                results["booking_created"] = True
                results["booking_id"] = bid
                logger.info(f"[LOGIC_PERSISTENCE] Reserva #{bid} criada com sucesso.")
            else:
                results["booking_error"] = res_booking.get("error")

        # 5. MONITORAMENTO E PAGAMENTO
        booking_id = updated_context.get("booking_id")
        if booking_id:
            booking = db.get(models.Booking, booking_id)
            if booking:
                results["booking_status"] = str(booking.status.value)
                results["payment_status"] = str(booking.payment_status.value)
                
                # Gera Info de Pagamento (Proativo se estiver em CONFIRMATION ou PAYMENT)
                is_payment_ready = (context.get("current_state") in ["CONFIRMATION", "PAYMENT"])
                if is_payment_ready or any(w in msg_lower for w in ["pagar", "link", "pix", "pagamento"]):
                    pay_info = payment_info_logic(tenant_id, booking_id)
                    
                    # Cálculo de sinal
                    setting = db.query(models.SystemSetting).filter(
                        models.SystemSetting.key == "pousada_deposit_percentage",
                        models.SystemSetting.tenant_id == tenant_id
                    ).first()
                    perc = float(setting.value) / 100.0 if (setting and setting.value) else 1.0
                    
                    results["payment"] = {
                        "type": "deposit",
                        "amount": booking.total_amount * perc,
                        "percentage": int(perc * 100),
                        "info": pay_info,
                        "booking_id": booking_id
                    }

        # 6. SINCRO CONTROL (AUDITORIA DE MUDANÇA DE IDEIA)
        # Se as datas mudaram, limpamos seleções de quarto e cotações antigas
        prev_ci = context.get("_last_ci")
        prev_co = context.get("_last_co")
        curr_ci = updated_context.get("check_in")
        curr_co = updated_context.get("check_out")
        
        if (curr_ci and curr_ci != prev_ci) or (curr_co and curr_co != prev_co):
            results["intent_shift"] = "dates_changed"
            updated_context["room_id"] = None
            updated_context["total_price"] = 0
            updated_context["booking_id"] = None # Reset reserva se mudar data
            results["quote"] = None
            updated_context["_last_ci"] = curr_ci
            updated_context["_last_co"] = curr_co
        
        prev_group = context.get("_last_group")
        curr_group = updated_context.get("group_size")
        if curr_group and curr_group != prev_group:
            results["intent_shift"] = "group_size_changed"
            if context.get("companions") and len(context["companions"]) > (curr_group - 1):
                updated_context["companions"] = context["companions"][:(curr_group - 1)]
            updated_context["_last_group"] = curr_group

    results["updated_context"] = updated_context
    return results

def get_raw_analytics_logic(
    tenant_id: int, 
    start_date: str = None, 
    end_date: str = None, 
    compare_with_previous: bool = False
) -> dict:
    """
    Fonte de dados analíticos para o robô. Consolida KPIs, 
    comparativos e breakdowns para que a IA realize a análise interpretativa.
    """
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            
            # 1. Normalização de Datas
            now = datetime.now()
            end = universal_date_parser(end_date) or now.date()
            start = universal_date_parser(start_date) or (end - timedelta(days=29))
            
            # Importamos o helper do finance.py se possível, ou replicamos a lógica para ser independente
            # replicaremos aqui para garantir que 'shared_tools' seja o ponto único de verdade para os agentes
            
            def get_summary(s: date, e: date):
                s_dt = datetime.combine(s, datetime.min.time())
                e_dt = datetime.combine(e, datetime.max.time())
                days = (e - s).days + 1
                
                revenue = db.query(func.coalesce(func.sum(models.Revenue.amount), 0.0)).filter(
                    models.Revenue.created_at >= s_dt, models.Revenue.created_at <= e_dt
                ).scalar() or 0.0
                
                expense = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
                    models.Expense.is_paid == True,
                    models.Expense.paid_date >= s, models.Expense.paid_date <= e
                ).scalar() or 0.0
                
                # Top Products (PDV Mix) - Top 5
                prod_mix = db.query(
                    models.PDVSaleItem.product_name, 
                    func.sum(models.PDVSaleItem.quantity),
                    func.sum(models.PDVSaleItem.total_item)
                ).join(models.PDVSale).filter(
                    models.PDVSale.created_at >= s_dt, models.PDVSale.created_at <= e_dt
                ).group_by(models.PDVSaleItem.product_name).order_by(desc(func.sum(models.PDVSaleItem.quantity))).limit(5).all()
                
                product_mix = [{"name": p[0], "qty": float(p[1]), "total": float(p[2])} for p in prod_mix]
                
                # Breakdown por Categoria (Receita)
                rev_cats = db.query(models.Revenue.category, func.sum(models.Revenue.amount)).filter(
                    models.Revenue.created_at >= s_dt, models.Revenue.created_at <= e_dt
                ).group_by(models.Revenue.category).all()
                by_category = {c.value if hasattr(c, 'value') else str(c): float(v) for c, v in rev_cats}
                
                # Ocupação
                total_rooms = db.query(models.Room).count() or 1
                checkins = db.query(models.Booking).filter(
                    models.Booking.real_check_in >= s_dt, models.Booking.real_check_in <= e_dt
                ).count()
                
                return {
                    "revenue": round(float(revenue), 2),
                    "expense": round(float(expense), 2),
                    "net": round(float(revenue) - float(expense), 2),
                    "checkins": checkins,
                    "product_mix": product_mix,
                    "by_category": by_category,
                    "occupancy_est": round((checkins / (total_rooms * days)) * 100, 1) if days > 0 else 0
                }

            current_period = get_summary(start, end)
            result = {
                "period": {"start": str(start), "end": str(end)},
                "current": current_period
            }
            
            if compare_with_previous:
                days_diff = (end - start).days + 1
                prev_end = start - timedelta(days=1)
                prev_start = prev_end - timedelta(days=days_diff - 1)
                previous_period = get_summary(prev_start, prev_end)
                
                def calc_delta(cur, prev):
                    diff = cur - prev
                    pct = round((diff / prev) * 100, 1) if prev != 0 else None
                    return {"abs": round(diff, 2), "pct": pct}

                result["comparison"] = {
                    "period": {"start": str(prev_start), "end": str(prev_end)},
                    "data": previous_period,
                    "deltas": {
                        "revenue": calc_delta(current_period["revenue"], previous_period["revenue"]),
                        "expense": calc_delta(current_period["expense"], previous_period["expense"]),
                        "net": calc_delta(current_period["net"], previous_period["net"]),
                        "checkins": calc_delta(current_period["checkins"], previous_period["checkins"])
                    }
                }
            
            return result
    except Exception as e:
        return {"error": f"Erro na análise de dados: {str(e)}"}
