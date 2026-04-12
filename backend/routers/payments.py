from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import hmac, hashlib, os
import models
from database import get_db, SessionLocal, set_tenant_context
from payments.mercadopago_service import MercadoPagoService, MercadoPagoUnavailable
from .auth import get_current_staff

router = APIRouter(prefix="/payments", tags=["Payments"])

def _cpf_digits(doc: str) -> str:
    return "".join([c for c in (doc or "") if c.isdigit()])

def _cpf_valid(doc: str) -> bool:
    s = _cpf_digits(doc)
    if len(s) != 11 or s == s[0] * 11:
        return False
    nums = [int(x) for x in s]
    sm = sum(nums[i] * (10 - i) for i in range(9))
    d1 = (sm * 10) % 11
    d1 = 0 if d1 == 10 else d1
    if d1 != nums[9]:
        return False
    sm = sum(nums[i] * (11 - i) for i in range(10))
    d2 = (sm * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return d2 == nums[10]

def compute_checkout_summary(db: Session, room_id: int):
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
    base_checkin = booking.real_check_in or booking.check_in_date
    duration = datetime.now() - base_checkin
    days = duration.days if duration.days > 0 else 1
    daily_total = days * booking.daily_rate
    consumption_total = sum([c.quantity * c.unit_price for c in booking.consumptions])
    return booking, daily_total, consumption_total, daily_total + consumption_total

@router.get("/summary/{room_id}")
def summary(room_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    booking, daily_total, consumption_total, grand_total = compute_checkout_summary(db, room_id)
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    guest = booking.guest
    return {
        "room_id": room_id,
        "room_number": room.number if room else "",
        "booking_id": booking.id,
        "guest_name": guest.name if guest else None,
        "guest_email": guest.email if guest else None,
        "daily_total": daily_total,
        "consumption_total": consumption_total,
        "grand_total": grand_total
    }

def perform_checkout(db: Session, room_id: int, method: models.PaymentMethod):
    booking = db.query(models.Booking).with_for_update().filter(
        models.Booking.room_id == room_id,
        models.Booking.status.in_([models.BookingStatus.ATIVO, models.BookingStatus.CONFIRMADO])
    ).order_by(models.Booking.check_in_date.desc()).first()
    if not booking:
        raise HTTPException(status_code=400, detail="Não há check-in ativo neste quarto")
    if booking.status == models.BookingStatus.CONCLUIDO:
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        return {"message": "Reserva já concluída", "total": booking.total_amount}
    room = db.query(models.Room).with_for_update().filter(models.Room.id == room_id).first()
    base_checkin = booking.real_check_in or booking.check_in_date
    duration = datetime.now() - base_checkin
    days = duration.days if duration.days > 0 else 1
    consumption_total = sum([c.quantity * c.unit_price for c in booking.consumptions])
    final_total = (days * booking.daily_rate) + consumption_total
    booking.status = models.BookingStatus.CONCLUIDO
    booking.real_check_out = datetime.now()
    booking.total_amount = final_total
    room.status = models.RoomStatus.LIMPEZA
    revenue_entry = models.Revenue(
        description=f"Check-out Quarto {room.number} - Reserva #{booking.id}",
        amount=final_total,
        category=models.RevenueCategory.HOSPEDAGEM,
        payment_method=method,
        booking_id=booking.id,
        created_at=datetime.now()
    )
    db.add(revenue_entry)
    db.commit()
    return {"message": "Check-out realizado e Receita Lançada", "total": final_total}

@router.post("/checkout/{room_id}/pix")
def start_pix_checkout(room_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable as e:
        raise HTTPException(status_code=500, detail=str(e))
    booking, daily_total, consumption_total, grand_total = compute_checkout_summary(db, room_id)
    metadata = {"room_id": room_id, "booking_id": booking.id, "type": "checkout", "tenant_id": current_user.tenant_id}
    description = f"Check-out Reserva #{booking.id} Quarto {booking.room.number if booking.room else ''}"
    env = (os.getenv("ENVIRONMENT") or "development").lower()
    guest = booking.guest
    payer = None
    try:
        if guest:
            full = (guest.name or "").strip()
            parts = [p for p in full.split() if p]
            first = parts[0] if parts else "Test"
            last = parts[-1] if len(parts) > 1 else "User"
            cpf = _cpf_digits(guest.document or "")
            if env == "production":
                if not _cpf_valid(cpf):
                    raise HTTPException(status_code=400, detail="CPF inválido para pagamento PIX")
            else:
                cpf = cpf if _cpf_valid(cpf) else "19119119100"
            email = guest.email if env == "production" else (guest.email or os.getenv("TEST_PAYER_EMAIL") or None)
            payer = {
                "email": email,
                "first_name": first,
                "last_name": last,
                "identification": {"type": "CPF", "number": cpf}
            }
    except Exception:
        payer = None
    result = mp.create_pix_payment(grand_total, description, metadata, payer=payer) or {}
    status_code = result.get("status")
    response = result.get("response") or {}
    if status_code and int(status_code) >= 400:
        error = {
            "error": response.get("error"),
            "message": response.get("message"),
            "cause": response.get("cause"),
        }
        print(f"[MP ERROR] create_pix_payment status={status_code} error={error}")
        return {
            "payment_id": None,
            "status": status_code,
            "amount": None,
            "qr_code": None,
            "qr_code_base64": None,
            "metadata": {},
            "error": error,
        }
    poi = (response.get("point_of_interaction") or {}).get("transaction_data") or {}
    return {
        "payment_id": response.get("id"),
        "status": response.get("status"),
        "amount": response.get("transaction_amount"),
        "qr_code": poi.get("qr_code"),
        "qr_code_base64": poi.get("qr_code_base64"),
        "metadata": response.get("metadata", {})
    }

@router.post("/checkout/{room_id}/card")
def start_card_checkout(room_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable as e:
        raise HTTPException(status_code=500, detail=str(e))
    booking, daily_total, consumption_total, grand_total = compute_checkout_summary(db, room_id)
    metadata = {"room_id": room_id, "booking_id": booking.id, "type": "checkout", "tenant_id": current_user.tenant_id}
    title = f"Check-out Reserva #{booking.id} Quarto {booking.room.number if booking.room else ''}"
    fe = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    back_urls = {
        "success": fe + "/payments",
        "pending": fe + "/payments",
        "failure": fe + "/payments"
    }
    result = mp.create_card_preference(grand_total, title, metadata, back_urls=back_urls) or {}
    status_code = result.get("status")
    response = result.get("response") or {}
    if status_code and int(status_code) >= 400:
        error = {
            "error": response.get("error"),
            "message": response.get("message"),
            "cause": response.get("cause"),
        }
        print(f"[MP ERROR] create_card_preference status={status_code} error={error}")
        return {
            "preference_id": None,
            "init_point": None,
            "sandbox_init_point": None,
            "status": status_code,
            "error": error,
        }
    return {
        "preference_id": response.get("id"),
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
        "status": 200
    }
@router.post("/public/{booking_id}/card")
def start_public_card(booking_id: int, tenant_id: int, db: Session = Depends(get_db)):
    set_tenant_context(db, tenant_id)
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable as e:
        raise HTTPException(status_code=500, detail=str(e))
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    amount = booking.total_amount or 0.0
    title = f"Reserva #{booking.id} Quarto {booking.room.number if booking.room else ''}"
    metadata = {"booking_id": booking.id, "type": "public", "tenant_id": tenant_id}
    fe = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    back_urls = {
        "success": fe + "/public/book",
        "pending": fe + "/public/book",
        "failure": fe + "/public/book"
    }
    result = mp.create_card_preference(amount, title, metadata, back_urls=back_urls) or {}
    status_code = result.get("status")
    response = result.get("response") or {}
    if status_code and int(status_code) >= 400:
        error = {"error": response.get("error"), "message": response.get("message"), "cause": response.get("cause")}
        print(f"[MP ERROR] public_card status={status_code} error={error}")
        return {
            "preference_id": None,
            "init_point": None,
            "sandbox_init_point": None,
            "status": status_code,
            "error": error,
        }
    return {
        "preference_id": response.get("id"),
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
        "status": 200
    }
@router.get("/status/{payment_id}")
def payment_status(payment_id: int):
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable as e:
        raise HTTPException(status_code=500, detail=str(e))
    status = mp.get_status(payment_id)
    return {"status": status}

@router.post("/webhook")
async def webhook(req: Request, db: Session = Depends(get_db)):
    raw = await req.body()
    secret = os.getenv("MP_WEBHOOK_SECRET")
    sig_header = req.headers.get("x-signature") or req.headers.get("X-Signature")
    if secret:
        if not sig_header:
            raise HTTPException(status_code=401, detail="Assinatura ausente")
        expected = hmac.new(bytes.fromhex(secret), raw, hashlib.sha256).hexdigest()
        provided = sig_header.split("=", 1)[-1].strip() if "=" in sig_header else sig_header.strip()
        if not hmac.compare_digest(expected, provided):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable:
        return {"ok": True}
    payload = await req.json()
    pid = None
    if isinstance(payload, dict):
        if payload.get("data") and isinstance(payload.get("data"), dict):
            pid = payload["data"].get("id")
        if not pid and payload.get("id"):
            pid = payload.get("id")
    if not pid:
        return {"ok": True}
    try:
        result = mp.get_payment(int(pid)) or {}
        response = result.get("response") or {}
        status = response.get("status")
        metadata = response.get("metadata") or {}
        
        # 1. Ativa contexto RLS para o Tenant apropriado do pagamento
        tenant_id = metadata.get("tenant_id")
        if tenant_id:
            set_tenant_context(db, int(tenant_id))

        if status == "approved":
            room_id = metadata.get("room_id")
            if room_id:
                try:
                    method = models.PaymentMethod.PIX
                    m_id = (response.get("payment_method_id") or "") or ""
                    m_type = (response.get("payment_type_id") or "") or ""
                    txt = f"{m_id}:{m_type}".lower()
                    if "credit" in txt:
                        method = models.PaymentMethod.CREDITO
                    perform_checkout(db, int(room_id), method)
                except Exception:
                    pass
            if (metadata.get("type") or "") == "public":
                booking_id = metadata.get("booking_id")
                if booking_id:
                    try:
                        booking = db.query(models.Booking).filter(models.Booking.id == int(booking_id)).first()
                        if booking:
                            booking.status = models.BookingStatus.CONFIRMADO
                            db.commit()
                    except Exception:
                        pass
    except Exception:
        pass
    return {"ok": True}

@router.get("/webhook")
def webhook_get(id: int | None = None, background_tasks: BackgroundTasks = None):
    if not id:
        return {"ok": True}
    def handle(pid: int):
        db = SessionLocal()
        try:
            try:
                mp = MercadoPagoService()
            except MercadoPagoUnavailable:
                return
            result = mp.get_payment(int(pid)) or {}
            response = result.get("response") or {}
            status = response.get("status")
            metadata = response.get("metadata") or {}
            
            tenant_id = metadata.get("tenant_id")
            if tenant_id:
                set_tenant_context(db, int(tenant_id))

            if status == "approved":
                room_id = metadata.get("room_id")
                if room_id:
                    try:
                        perform_checkout(db, int(room_id), models.PaymentMethod.PIX)
                    except Exception:
                        pass
                if (metadata.get("type") or "") == "public":
                    booking_id = metadata.get("booking_id")
                    if booking_id:
                        try:
                            booking = db.query(models.Booking).filter(models.Booking.id == int(booking_id)).first()
                            if booking:
                                booking.status = models.BookingStatus.CONFIRMADO
                                db.commit()
                        except Exception:
                            pass
        finally:
            db.close()
    try:
        if background_tasks is not None:
            background_tasks.add_task(handle, int(id))
    except Exception:
        pass
    return {"ok": True}
