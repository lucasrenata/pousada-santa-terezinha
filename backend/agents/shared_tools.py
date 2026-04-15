import os
import json
import models
from sqlalchemy.orm import Session
from database import SessionLocal, set_tenant_context
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from datetime import datetime, date, timedelta
from typing import Optional, List
from utils.payment_helpers import prepare_payer_data, process_mp_response

# --- UTILS DE DATA (UNIVERSAL) ---
def universal_date_parser(date_str):
    """Interpreta datas em formato DD/MM, DD/MM/YYYY ou YYYY-MM-DD."""
    if not date_str: return None
    date_str = date_str.strip()
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
    days = calculate_daily_rates_count(ci, co)
    settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
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

    fds_rule = next((r for r in active_rules if r.name == "Tarifa Fim de Semana"), None)
    if fds_rule:
        has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
        if has_weekend:
            mult = float(fds_rule.config.get("multiplier", 1.2))
            total_amount *= mult
            note_parts.append(f"Ajuste FDS (x{mult})")

    return {"total": total_amount, "days": days, "notes": " | ".join(note_parts), "event_name": event.name if event else None}

# --- LOGICAS ATOMICAS ---
def find_guest_logic(tenant_id: int, cpf: str = "", name: str = "", base_url: str = "") -> dict:
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        if cpf:
            clean_cpf = "".join(filter(str.isdigit, cpf))
            g = db.query(models.Guest).filter(models.Guest.document == clean_cpf).first()
            if g: return {"id": g.id, "name": g.name, "cpf": g.document}
        
        prefix = base_url.rstrip("/") if base_url else ""
        link = f"{prefix}/{tenant_id}/registrar?cpf={''.join(filter(str.isdigit, cpf)) if cpf else ''}"
        return {"error": "Hóspede não encontrado.", "registration_link": link}

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
            days = calculate_daily_rates_count(ci, co, settings.get("check_in_time", "14:00"), settings.get("check_out_time", "12:00"))
            
            occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date > ci, models.Booking.check_in_date < co
            ).all()]
            rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()
            
            final_rooms = []
            for r in rooms:
                if r.max_capacity >= group_size:
                    quote = calculate_booking_quote(db, tenant_id, r.id, ci, co, group_size, ages)
                    final_rooms.append({"room_number": r.id, "type": r.type or "Quarto", "total_quote": quote["total"], "notes": quote["notes"]})

            return {"available_options": final_rooms, "summary": f"Encontrei {len(final_rooms)} quartos."}
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

def booking_creation_logic(tenant_id: int, guest_id: int, room_id: str, check_in: str, check_out: str, group_size: int, companions: List[dict] = [], mode: str = "NORMAL") -> dict:
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            ci = universal_date_parser(check_in)
            co = universal_date_parser(check_out)
            guest = db.query(models.Guest).get(guest_id)
            ages = [guest.age or 18] + [int(c.get('age', 18)) for c in companions]
            quote = calculate_booking_quote(db, tenant_id, room_id, ci, co, group_size, ages)

            booking = models.Booking(
                guest_id=guest_id, room_id=room_id, check_in_date=ci, check_out_date=co,
                total_guests=group_size, total_amount=quote["total"], 
                status=models.BookingStatus.PENDENTE, notes=quote["notes"]
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            for c in companions:
                db.add(models.Companion(booking_id=booking.id, name=c['name'], age=int(c.get('age', 18))))
            db.commit()
            return {"success": True, "booking_id": booking.id, "total": quote["total"]}
    except Exception as e:
        return {"error": str(e)}

def payment_info_logic(tenant_id: int, booking_id: int) -> dict:
    try:
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(booking_id)
            config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == tenant_id, models.TenantConfig.is_active == True).first()
            manual_key = config.manual_pix_key if config else None
            qr_data = None
            try:
                from payments.mercadopago_service import MercadoPagoService
                from routers.payments import get_tenant_mp_token
                token = get_tenant_mp_token(db, tenant_id)
                if token:
                    mp = MercadoPagoService()
                    payer = prepare_payer_data(booking.guest)
                    res = mp.create_pix_payment(token, tenant_id, booking.total_amount, f"Reserva #{booking.id}", {"booking_id": booking.id}, payer=payer)
                    payment_result = process_mp_response(res)
                    if payment_result.get("qr_code"):
                        qr_data = {"image": payment_result.get("qr_code_base64"), "code": payment_result.get("qr_code"), "link": payment_result.get("payment_url")}
            except: pass
            
            if not qr_data:
                global_pix = db.query(models.SystemSetting).filter(models.SystemSetting.key == "pousada_pix_key").first()
                manual_key = manual_key or (global_pix.value if global_pix else None)

            return {"booking_id": booking_id, "total": booking.total_amount, "pix_qr": qr_data, "manual_key": manual_key}
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
