from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional
import asyncio, json
import models, schemas
from database import get_db, set_tenant_context
from .auth import get_current_staff
from utils.email_sender import send_booking_confirmation
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# 1. CRIAR RESERVA (Vem do Formulário Web)
@router.post("/")
async def create_booking(data: schemas.BookingCreate, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    try:
        # --- VALIDAÇÃO DE CAPACIDADE MÁXIMA ---
        if data.room_id:
            room = db.query(models.Room).filter(models.Room.id == data.room_id).first()
            if not room:
                raise HTTPException(status_code=404, detail="Quarto não encontrado no sistema.")
                
            total_people = 1 + len(data.companions)
            if data.mode == models.BookingMode.CARAVANA:
                total_people = data.total_guests
                
            if total_people > room.max_capacity:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Capacidade excedida! O quarto {room.id} comporta no máximo {room.max_capacity} pessoas."
                )

            # Verifica conflito de datas
            conflict = db.query(models.Booking).filter(
                models.Booking.room_id == data.room_id,
                models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
                models.Booking.check_out_date > data.check_in_date,
                models.Booking.check_in_date < data.check_out_date,
            ).first()
            if conflict:
                raise HTTPException(status_code=400, detail="Este quarto já possui uma reserva confirmada para o período selecionado.")

        # Busca Hóspede para validação e cálculo
        guest = db.query(models.Guest).filter(models.Guest.id == data.guest_id).first()
        if not guest:
            raise HTTPException(status_code=400, detail="Hóspede principal não localizado. Por favor, selecione ou cadastre um hóspede.")

        # Cálculo de dias e valores
        days = calculate_daily_rates_count(
            data.check_in_date, 
            data.check_out_date, 
            data.check_in_time, 
            data.check_out_time
        )
        
        guest_age = 18
        if guest.birth_date:
            today = date.today()
            guest_age = today.year - guest.birth_date.year - ((today.month, today.day) < (guest.birth_date.month, guest.birth_date.day))
        
        ages = [guest_age] + [c.age for c in data.companions]
        
        settings_rows = db.query(models.SystemSetting).all()
        settings_dict = {s.key: s.value for s in settings_rows}
        
        pricing = calculate_reservation_total(data.daily_rate, days, ages, settings=settings_dict)
        total_val = pricing["total"]

        # Cria a reserva
        booking = models.Booking(
            guest_id=data.guest_id,
            room_id=data.room_id, 
            check_in_date=data.check_in_date,
            check_out_date=data.check_out_date,
            check_in_time=data.check_in_time,
            check_out_time=data.check_out_time,
            mode=data.mode,
            total_guests=total_people,
            daily_rate=data.daily_rate,
            total_amount=total_val,
            notes=data.notes,
            status=models.BookingStatus.PENDENTE
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        # Adiciona Acompanhantes
        for comp in data.companions:
            new_comp = models.Companion(booking_id=booking.id, name=comp.name, age=comp.age)
            db.add(new_comp)
        
        db.commit()

        # --- DISPARO DE EMAIL AUTOMÁTICO ---
        try:
            if guest and guest.email:
                checkin_fmt = data.check_in_date.strftime("%d/%m/%Y")
                await send_booking_confirmation(guest.email, guest.name, checkin_fmt, booking.id)
        except Exception as e:
            print(f"⚠️ Erro ao enviar email de confirmação: {e}")

        return {"message": "Reserva criada com sucesso!", "booking_id": booking.id}

    except HTTPException:
        # Relança exceções controladas da FastAPI
        raise
    except Exception as e:
        # Captura erros inesperados e transforma em 400 amigável
        print(f"❌ Erro crítico ao criar reserva: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=400, 
            detail=f"Não foi possível efetivar a reserva. Motivo técnico: {str(e)}"
        )


# 2. CHECK-IN (Transforma reserva pendente em ativa)
@router.post("/checkin")
def check_in(data: schemas.CheckInRequest, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).with_for_update().filter(models.Booking.id == data.booking_id).first()
    if not booking: 
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    if booking.status not in [models.BookingStatus.PENDENTE, models.BookingStatus.CONFIRMADO]:
        raise HTTPException(status_code=400, detail="Reserva não está elegível para check-in")
    existing_active = db.query(models.Booking).filter(
        models.Booking.guest_id == booking.guest_id,
        models.Booking.status == models.BookingStatus.ATIVO
    ).first()
    if existing_active:
        room_active = db.query(models.Room).filter(models.Room.id == existing_active.room_id).first()
        room_num = room_active.id if room_active else ""
        raise HTTPException(status_code=400, detail=f"Hóspede já está com check-in ativo no quarto {room_num}")
    
    room = db.query(models.Room).with_for_update().filter(models.Room.id == data.room_id).first()
    if room.status != models.RoomStatus.DISPONIVEL:
         raise HTTPException(status_code=400, detail="Quarto Ocupado")

    # Atualiza Reserva
    booking.room_id = room.id
    booking.status = models.BookingStatus.ATIVO
    booking.real_check_in = datetime.now()
    
    # Bloqueia Quarto
    room.status = models.RoomStatus.OCUPADO
    
    db.commit()
    return {"message": "Check-in Confirmado!"}


# 3. CHECK-OUT (Com lançamento no Financeiro)
@router.post("/checkout/{room_id}")
def check_out(room_id: str, data: schemas.CheckoutPaymentRequest, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).with_for_update().filter(
        models.Booking.room_id == room_id, 
        models.Booking.status == models.BookingStatus.ATIVO
    ).first()
    if not booking:
        booking = db.query(models.Booking).with_for_update().filter(
            models.Booking.room_id == room_id,
            models.Booking.status == models.BookingStatus.CONFIRMADO
        ).order_by(models.Booking.check_in_date.desc()).first()
        if not booking:
            raise HTTPException(status_code=400, detail="Não há check-in ativo neste quarto")

    room = db.query(models.Room).with_for_update().filter(models.Room.id == room_id).first()

    # Recalcula com dados reais e lógica hoteleira
    base_checkin = booking.real_check_in or booking.check_in_date
    now = datetime.now()
    
    # Formata horários para a função de cálculo
    ci_time = booking.check_in_time
    co_time = now.strftime("%H:%M")
    
    days = calculate_daily_rates_count(base_checkin, now, ci_time, co_time)
    
    # Recalcula valor das diárias baseado nas idades originais
    guest_age = 18
    if booking.guest and booking.guest.birth_date:
        today = date.today()
        bday = booking.guest.birth_date
        guest_age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))
    
    ages = [guest_age] + [c.age for c in booking.companions]
    
    # Busca settings para o cálculo
    settings_rows = db.query(models.SystemSetting).all()
    settings_dict = {s.key: s.value for s in settings_rows}
    
    pricing = calculate_reservation_total(booking.daily_rate, days, ages, settings=settings_dict)
    
    consumption_total = sum([c.quantity * c.unit_price for c in booking.consumptions])
    final_total = pricing["total"] + consumption_total

    # Atualiza Status da Reserva
    booking.status = models.BookingStatus.CONCLUIDO
    booking.real_check_out = datetime.now()
    booking.total_amount = final_total
    
    # Atualiza Status do Quarto
    room.status = models.RoomStatus.LIMPEZA
    
    # --- LANÇAMENTO AUTOMÁTICO NO LIVRO CAIXA (FINANCEIRO) ---
    revenue_entry = models.Revenue(
        description=f"Check-out Quarto {room.id} - Reserva #{booking.id}",
        amount=final_total,
        category=models.RevenueCategory.HOSPEDAGEM,
        payment_method=data.payment_method,
        booking_id=booking.id,
        created_at=datetime.now()
    )
    db.add(revenue_entry)

    db.commit()

    return {"message": "Check-out realizado e Receita Lançada", "total": final_total}

# 3.1. RESUMO PARA CHECK-OUT (diárias x consumos)
@router.get("/summary/{room_id}")
def checkout_summary(room_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(
        models.Booking.room_id == room_id, 
        models.Booking.status == models.BookingStatus.ATIVO
    ).first()
    if not booking:
        booking = db.query(models.Booking).filter(
            models.Booking.room_id == room_id,
            models.Booking.status == models.BookingStatus.CONFIRMADO
        ).order_by(models.Booking.check_in_date.desc()).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Sem reserva ativa neste quarto")
    # Recalcula com dados reais e lógica hoteleira
    base_checkin = booking.real_check_in or booking.check_in_date
    now = datetime.now()
    
    ci_time = booking.check_in_time
    co_time = now.strftime("%H:%M")
    
    days = calculate_daily_rates_count(base_checkin, now, ci_time, co_time)
    
    # Recalcula valor das diárias baseado nas idades
    guest_age = 18
    if booking.guest and booking.guest.birth_date:
        today = date.today()
        bday = booking.guest.birth_date
        guest_age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))
    
    ages = [guest_age] + [c.age for c in booking.companions]
    
    # Busca settings para o cálculo
    settings_rows = db.query(models.SystemSetting).all()
    settings_dict = {s.key: s.value for s in settings_rows}
    
    pricing = calculate_reservation_total(booking.daily_rate, days, ages, settings=settings_dict)
    
    consumption_total = sum([c.quantity * c.unit_price for c in booking.consumptions])
    
    return {
        "booking_id": booking.id,
        "room_id": room_id,
        "days": days,
        "daily_rate": booking.daily_rate,
        "daily_total": pricing["total"],
        "consumption_total": consumption_total,
        "grand_total": pricing["total"] + consumption_total,
        "breakdown": pricing["breakdown"],
        "consumptions": [
            { 
                "product_id": c.product_id, 
                "product_name": c.product.name if c.product else "N/A",
                "quantity": c.quantity, 
                "unit_price": c.unit_price,
                "total": c.quantity * c.unit_price
            }
            for c in booking.consumptions
        ]
    }

@router.get("/stats/today")
def stats_today(db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    checkins = db.query(models.Booking).filter(
        models.Booking.real_check_in.isnot(None),
        models.Booking.real_check_in >= start,
        models.Booking.real_check_in < end
    ).count()
    checkouts = db.query(models.Booking).filter(
        models.Booking.real_check_out.isnot(None),
        models.Booking.real_check_out >= start,
        models.Booking.real_check_out < end
    ).count()
    return {"checkins": int(checkins), "checkouts": int(checkouts)}

@router.get("/stats/stream")
async def stats_stream(db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    async def event_gen():
        while True:
            try:
                start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                checkins = db.query(models.Booking).filter(
                    models.Booking.real_check_in.isnot(None),
                    models.Booking.real_check_in >= start,
                    models.Booking.real_check_in < end
                ).count()
                checkouts = db.query(models.Booking).filter(
                    models.Booking.real_check_out.isnot(None),
                    models.Booking.real_check_out >= start,
                    models.Booking.real_check_out < end
                ).count()
                payload = {"checkins": int(checkins), "checkouts": int(checkouts)}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)
    return StreamingResponse(event_gen(), media_type="text/event-stream")
# 4. LISTAR RESERVAS POR PERÍODO (para Calendário)
@router.get("/", response_model=List[schemas.BookingResponse])
def list_bookings(start: Optional[date] = None, end: Optional[date] = None, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    query = db.query(models.Booking)
    if start and end:
        query = query.filter(models.Booking.check_in_date <= end, models.Booking.check_out_date >= start)
    elif start:
        query = query.filter(models.Booking.check_out_date >= start)
    elif end:
        query = query.filter(models.Booking.check_in_date <= end)
    bookings = query.all()
    response = []
    for b in bookings:
        response.append({
            "id": b.id,
            "room_id": b.room_id,
            "room_number": b.room_id if b.room_id else None,
            "guest_id": b.guest_id,
            "guest_name": b.guest.name if b.guest else "",
            "guest_age": b.guest.age if b.guest else None,
            "mode": b.mode,
            "daily_rate": b.daily_rate,

            "status": b.status,
            "total_guests": b.total_guests,
            "total_amount": b.total_amount,
            "deposit_amount": b.deposit_amount,
            "payment_status": b.payment_status,
            "check_in_date": b.check_in_date,
            "check_out_date": b.check_out_date,
            "check_in_time": b.check_in_time,
            "check_out_time": b.check_out_time,
            "notes": b.notes,
            "companions": b.companions
        })
    return response

# 5. BUSCAR RESERVA ATIVA POR QUARTO (para mostrar no modal de quarto)
@router.get("/active/{room_id}")
def get_active_booking(room_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(
        models.Booking.room_id == room_id,
        models.Booking.status == models.BookingStatus.ATIVO
    ).first()
    if not booking:
        booking = db.query(models.Booking).filter(
            models.Booking.room_id == room_id,
            models.Booking.status == models.BookingStatus.CONFIRMADO
        ).order_by(models.Booking.check_in_date.desc()).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Sem reserva ativa neste quarto")
    guest_name = booking.guest.name if booking.guest else ""
    return {
        "id": booking.id,
        "guest_name": guest_name,
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
    }

@router.get("/availability", response_model=List[schemas.RoomResponse])
def get_availability(start: datetime, end: datetime, guests: Optional[int] = None, exclude_booking_id: Optional[int] = None, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    blocked_q = db.query(models.Booking.room_id).filter(
        models.Booking.room_id.isnot(None),
        models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
        models.Booking.check_out_date > start,
        models.Booking.check_in_date < end,
    )
    
    if exclude_booking_id:
        blocked_q = blocked_q.filter(models.Booking.id != exclude_booking_id)
        
    blocked_ids = {rid for (rid,) in blocked_q.distinct().all()}
    query = db.query(models.Room)
    if guests is not None:
        query = query.filter(models.Room.max_capacity >= guests)
    rooms = query.all()
    available = [r for r in rooms if r.id not in blocked_ids]
    return available

@router.get("/availability/public", response_model=List[schemas.RoomResponse])
def get_public_availability(tenant_id: int, start: datetime, end: datetime, guests: Optional[int] = None, exclude_booking_id: Optional[int] = None, db: Session = Depends(get_db)):
    set_tenant_context(db, tenant_id)
    blocked_q = db.query(models.Booking.room_id).filter(
        models.Booking.room_id.isnot(None),
        models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
        models.Booking.check_out_date > start,
        models.Booking.check_in_date < end,
    )
    if exclude_booking_id:
        blocked_q = blocked_q.filter(models.Booking.id != exclude_booking_id)
        
    blocked_ids = {rid for (rid,) in blocked_q.distinct().all()}
    query = db.query(models.Room)
    if guests is not None:
        query = query.filter(models.Room.max_capacity >= guests)
    rooms = query.all()
    available = [r for r in rooms if r.id not in blocked_ids]
    return available

@router.post("/reschedule")
def reschedule(data: schemas.RescheduleRequest, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).with_for_update().filter(models.Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    if booking.status not in [models.BookingStatus.PENDENTE, models.BookingStatus.CONFIRMADO]:
        raise HTTPException(status_code=400, detail="Apenas reservas pendentes ou confirmadas podem ser remanejadas")
    target_room_id = data.room_id if data.room_id is not None else booking.room_id
    if target_room_id:
        room = db.query(models.Room).with_for_update().filter(models.Room.id == target_room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Quarto não encontrado")
        total_people = booking.total_guests
        if total_people > room.max_capacity:
            raise HTTPException(status_code=400, detail="Capacidade excedida para o quarto selecionado")
        conflict = db.query(models.Booking).filter(
            models.Booking.room_id == target_room_id,
            models.Booking.id != booking.id,
            models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
            models.Booking.check_out_date > data.check_in_date,
            models.Booking.check_in_date < data.check_out_date,
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Quarto indisponível no período")
    booking.room_id = target_room_id
    booking.check_in_date = data.check_in_date
    booking.check_out_date = data.check_out_date
    days = (data.check_out_date - data.check_in_date).days
    if days < 1:
        days = 1
    booking.total_amount = days * booking.daily_rate
    db.commit()
    return {"message": "Reserva remanejada"}

# 6. CRIAR RESERVA PÚBLICA (Formulário do hóspede)
@router.post("/public")
async def create_public_booking(data: schemas.BookingPublicCreate, db: Session = Depends(get_db)):
    # 0. Set tenant context BEFORE queries
    set_tenant_context(db, data.tenant_id)
    
    # 1. Localiza ou cria hóspede
    g = data.guest
    guest = db.query(models.Guest).filter(models.Guest.document == g.document).first()
    if not guest:
        new_g_dict = g.model_dump(exclude={'tenant_id'})
        guest = models.Guest(
            name=g.name, email=g.email, phone=g.phone, document=g.document, birth_date=g.birth_date,
            profession=g.profession, address_zip=g.address_zip, address_street=g.address_street,
            address_number=g.address_number, address_neighborhood=g.address_neighborhood,
            address_city=g.address_city, address_state=g.address_state
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)
    else:
        # Atualiza dados se já existir
        guest.name = g.name
        guest.email = g.email
        guest.phone = g.phone
        guest.birth_date = g.birth_date
        db.commit()

    # 2. Valida capacidade
    total_people = 1 + len(data.companions)
    if data.mode == models.BookingMode.CARAVANA:
        total_people = data.total_guests

    if data.room_id:
        room = db.query(models.Room).filter(models.Room.id == data.room_id).first()
        if room and total_people > room.max_capacity:
            raise HTTPException(status_code=400, detail="Capacidade excedida")

    # 3. Cálculo de preços e datas
    days = calculate_daily_rates_count(data.check_in_date, data.check_out_date, data.check_in_time, data.check_out_time)
    
    guest_age = 18
    if guest.birth_date:
        today = date.today()
        guest_age = today.year - guest.birth_date.year - ((today.month, today.day) < (guest.birth_date.month, guest.birth_date.day))
    
    ages = [guest_age] + [c.age for c in data.companions]
    
    settings_rows = db.query(models.SystemSetting).all()
    settings_dict = {s.key: s.value for s in settings_rows}
    
    pricing = calculate_reservation_total(data.daily_rate, days, ages, settings=settings_dict)

    # 4. Cria reserva
    booking = models.Booking(
        guest_id=guest.id,
        room_id=data.room_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        check_in_time=data.check_in_time,
        check_out_time=data.check_out_time,
        mode=data.mode,
        total_guests=total_people,
        daily_rate=data.daily_rate,
        total_amount=pricing["total"],
        notes=data.notes,
        status=models.BookingStatus.PENDENTE
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    for comp in data.companions:
        db.add(models.Companion(booking_id=booking.id, name=comp.name, age=comp.age))
    db.commit()

    return {"message": "Solicitação recebida!", "booking_id": booking.id}

# 7. LER RESERVA ESPECÍFICA
@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_booking(booking_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    
    return {
        "id": booking.id,
        "room_id": booking.room_id,
        "room_number": booking.room_id if booking.room_id else None,
        "guest_id": booking.guest_id,
        "guest_name": booking.guest.name if booking.guest else "",
        "guest_age": booking.guest.age if booking.guest else None,
        "mode": booking.mode,
        "daily_rate": booking.daily_rate,
        "status": booking.status,
        "total_guests": booking.total_guests,
        "total_amount": booking.total_amount,
        "deposit_amount": booking.deposit_amount,
        "payment_status": booking.payment_status,
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
        "check_in_time": booking.check_in_time,
        "check_out_time": booking.check_out_time,
        "notes": booking.notes,
        "companions": booking.companions
    }

# 8. ATUALIZAR RESERVA
@router.put("/{booking_id}")
def update_booking(booking_id: int, data: schemas.BookingUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Previne que o frontend sobrescreva os hóspedes calculados
    if "total_guests" in update_data:
        update_data.pop("total_guests")
        
    if "companions" in update_data:
        comps = update_data.pop("companions")
        # Remove acompanhantes antigos
        db.query(models.Companion).filter(models.Companion.booking_id == booking_id).delete()
        # Adiciona novos
        for c in comps:
            db.add(models.Companion(booking_id=booking.id, name=c['name'], age=c['age']))
            
        booking.total_guests = 1 + len(comps)

    for key, value in update_data.items():
        setattr(booking, key, value)
        
    db.commit()
    db.refresh(booking)
    
    # Recalcula o valor total da reserva após a atualização dos dados
    settings_rows = db.query(models.SystemSetting).all()
    settings_dict = {s.key: s.value for s in settings_rows}
    
    days = calculate_daily_rates_count(
        booking.check_in_date, 
        booking.check_out_date, 
        booking.check_in_time, 
        booking.check_out_time
    )
    
    guest_age = 18
    if booking.guest and booking.guest.birth_date:
        today = date.today()
        bday = booking.guest.birth_date
        guest_age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))
        
    ages = [guest_age] + [c.age for c in booking.companions]
    pricing = calculate_reservation_total(booking.daily_rate, days, ages, settings=settings_dict)
    booking.total_amount = pricing["total"]
    
    db.commit()
    db.refresh(booking)
    return {"message": "Reserva atualizada com sucesso"}

# 9. DELETAR RESERVA
@router.delete("/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    
    db.query(models.Companion).filter(models.Companion.booking_id == booking_id).delete()
    db.delete(booking)
    db.commit()
    return {"message": "Reserva deletada com sucesso"}
