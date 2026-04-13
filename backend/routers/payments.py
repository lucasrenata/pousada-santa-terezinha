from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import hmac, hashlib, os
import models
from database import get_db, SessionLocal, set_tenant_context
from payments.mercadopago_service import MercadoPagoService, MercadoPagoUnavailable
from .auth import get_current_staff
from core.crypto import CryptoService
from pydantic import BaseModel

router = APIRouter(prefix="/payments", tags=["Payments"])

class TokenTestRequest(BaseModel):
    token: str

def get_tenant_mp_token(db: Session, tenant_id: int):
    config = db.query(models.TenantConfig).filter(
        models.TenantConfig.tenant_id == tenant_id, 
        models.TenantConfig.is_active == True
    ).first()
    
    if not config or not config.mp_access_token:
        # Fallback para o env se não houver config no DB
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            raise HTTPException(status_code=400, detail="Configuração do Mercado Pago não encontrada para este Tenant")
        return token
    
    crypto = CryptoService()
    try:
        return crypto.decrypt_token(config.mp_access_token)
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao descriptografar token do Mercado Pago")

@router.post("/test-config")
def test_mp_config(req: TokenTestRequest, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    token = req.token.strip() if req.token else ""
    
    # Diagnóstico Seguro
    token_source = "INPUT" if req.token else "DATABASE"
    
    if not token:
        try:
            token = get_tenant_mp_token(db, current_user.tenant_id)
        except Exception:
            return {"valid": False, "message": "Falha na descriptografia ou token não encontrado."}

    print(f"[MP DIAGNOSTIC] Iniciando teste de conexão. Fonte: {token_source}")
    if token:
        print(f"[MP DIAGNOSTIC] Token para teste: {token[:6]}... (Tamanho: {len(token)})")
    else:
        print("[MP DIAGNOSTIC] ERRO: Token está vazio após processamento.")
        
    mp = MercadoPagoService()
    is_valid = mp.test_connection(token)
    print(f"[MP DIAGNOSTIC] Resultado do Mercado Pago: {'VÁLIDO' if is_valid else 'INVÁLIDO'}")
    return {"valid": is_valid}

class ConfigSaveRequest(BaseModel):
    mp_access_token: str
    mp_public_key: str
    manual_pix_key: str | None = None

@router.get("/config")
def get_mp_config(db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == current_user.tenant_id).first()
    if not config:
        return {"mp_public_key": "", "has_token": False, "manual_pix_key": ""}
    return {
        "mp_public_key": config.mp_public_key,
        "has_token": bool(config.mp_access_token),
        "manual_pix_key": config.manual_pix_key or "",
        "is_active": config.is_active
    }

@router.post("/config")
def save_mp_config(req: ConfigSaveRequest, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    crypto = CryptoService()
    # Limpeza de espaços no momento do salvamento
    clean_token = req.mp_access_token.strip()
    clean_public_key = req.mp_public_key.strip()
    clean_manual_pix = req.manual_pix_key.strip() if req.manual_pix_key else None
    
    encrypted_token = crypto.encrypt_token(clean_token)
    
    config = db.query(models.TenantConfig).filter(models.TenantConfig.tenant_id == current_user.tenant_id).first()
    if not config:
        config = models.TenantConfig(
            tenant_id=current_user.tenant_id,
            mp_access_token=encrypted_token,
            mp_public_key=clean_public_key,
            manual_pix_key=clean_manual_pix
        )
        db.add(config)
    else:
        config.mp_access_token = encrypted_token
        config.mp_public_key = req.mp_public_key
        config.manual_pix_key = req.manual_pix_key
        config.is_active = True
        
    db.commit()
    return {"message": "Configuração salva com sucesso!"}

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

def compute_checkout_summary(db: Session, room_id: str):
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
def summary(room_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
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

def perform_checkout(db: Session, room_id: str, method: models.PaymentMethod):
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
def start_pix_checkout(room_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
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
    result = mp.create_pix_payment(token, current_user.tenant_id, grand_total, description, metadata, payer=payer) or {}
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
def start_card_checkout(room_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_staff)):
    try:
        mp = MercadoPagoService()
    except MercadoPagoUnavailable as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    token = get_tenant_mp_token(db, current_user.tenant_id)
    booking, daily_total, consumption_total, grand_total = compute_checkout_summary(db, room_id)
    metadata = {"room_id": room_id, "booking_id": booking.id, "type": "checkout", "tenant_id": current_user.tenant_id}
    title = f"Check-out Reserva #{booking.id} Quarto {booking.room.number if booking.room else ''}"
    fe = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    back_urls = {
        "success": fe + "/payments",
        "pending": fe + "/payments",
        "failure": fe + "/payments"
    }
    result = mp.create_card_preference(token, current_user.tenant_id, grand_total, title, metadata, back_urls=back_urls) or {}
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
    
    token = get_tenant_mp_token(db, tenant_id)
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
    result = mp.create_card_preference(token, tenant_id, amount, title, metadata, back_urls=back_urls) or {}
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
    
    # Nota: get_status dinâmico precisaria de tenant_id aqui. 
    # Como este endpoint é simples, tentaremos com o token global se disponível.
    token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
    status = mp.get_status(payment_id) # Este método mp.get_status ainda não foi refatado para token dinâmico no service
    return {"status": status}

def handle_mercadopago_payment(pid: int, db: Session):
    """Processamento pesado em background para evitar timeouts do Mercado Pago"""
    try:
        mp = MercadoPagoService()
        # 1. Tenta inicialmente com o token global para descobrir o tenant
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        
        result = mp.get_payment(token, int(pid)) or {}
        response = result.get("response") or {}
        
        ext_ref = response.get("external_reference")
        tenant_id = None
        booking_id = None
        
        # Extração de Identidade (Tenant e Reserva)
        if ext_ref and ":" in str(ext_ref):
            try:
                parts = str(ext_ref).split(":")
                tenant_id = int(parts[0])
                booking_id = int(parts[1])
            except:
                pass
        
        if not tenant_id:
            # Fallback para metadata
            metadata = response.get("metadata") or {}
            tenant_id = metadata.get("tenant_id")
            booking_id = metadata.get("booking_id")
            
        if not tenant_id:
            print(f"[WEBHOOK WARNING] Pagamento {pid} sem tenant_id identificado.")
            return

        # 2. Troca de Contexto e Descriptografia
        set_tenant_context(db, int(tenant_id))
        token = get_tenant_mp_token(db, int(tenant_id))
        
        # 3. Re-validação com o token do dono do pagamento
        result = mp.get_payment(token, int(pid)) or {}
        response = result.get("response") or {}
        
        status = response.get("status")
        amount = response.get("transaction_amount")
        metadata = response.get("metadata") or {}
        
        if status == "approved":
            # Automação de Reserva
            if booking_id:
                booking = db.query(models.Booking).filter(models.Booking.id == int(booking_id)).first()
                if booking and booking.status != models.BookingStatus.CONFIRMADO:
                    booking.status = models.BookingStatus.CONFIRMADO
                    
                    # Automação Financeira: Registro de Receita
                    method = models.PaymentMethod.PIX
                    m_id = (response.get("payment_method_id") or "").lower()
                    if "credit" in m_id or "card" in m_id:
                        method = models.PaymentMethod.CREDITO
                    
                    revenue_entry = models.Revenue(
                        description=f"Pagamento MP #{pid} - Reserva #{booking.id}",
                        amount=float(amount),
                        category=models.RevenueCategory.HOSPEDAGEM,
                        payment_method=method,
                        booking_id=booking.id,
                        tenant_id=int(tenant_id),
                        created_at=datetime.now()
                    )
                    db.add(revenue_entry)
                    db.commit()
                    print(f"[WEBHOOK SUCCESS] Tenant {tenant_id}: Reserva {booking_id} paga e receita lançada.")

            # Checkout Automático se for do tipo 'checkout'
            if (metadata.get("type") or "") == "checkout":
                room_id = metadata.get("room_id")
                if room_id:
                    try:
                        perform_checkout(db, int(room_id), models.PaymentMethod.PIX)
                    except:
                        pass
    except Exception as e:
        print(f"[WEBHOOK BACKGROUND ERROR] Payment {pid}: {e}")

@router.post("/webhook")
async def webhook(req: Request, background_tasks: BackgroundTasks):
    try:
        # Validação Rápida de Segurança
        secret = os.getenv("MP_WEBHOOK_SECRET")
        sig_header = req.headers.get("x-signature") or req.headers.get("X-Signature")
        if secret and sig_header:
            raw = await req.body()
            expected = hmac.new(bytes.fromhex(secret), raw, hashlib.sha256).hexdigest()
            provided = sig_header.split("=", 1)[-1].strip() if "=" in sig_header else sig_header.strip()
            if not hmac.compare_digest(expected, provided):
                raise HTTPException(status_code=401, detail="Assinatura inválida")

        payload = await req.json()
        pid = None
        if isinstance(payload, dict):
            if payload.get("data") and isinstance(payload.get("data"), dict):
                pid = payload["data"].get("id")
            if not pid and payload.get("id"):
                pid = payload.get("id")
        
        if pid:
            # Envia para processamento em background e libera o Mercado Pago imediatamente
            db = SessionLocal()
            background_tasks.add_task(handle_mercadopago_payment, int(pid), db)
            
    except Exception as e:
        print(f"[WEBHOOK POST ERROR] {e}")
        
    return {"ok": True}

@router.get("/webhook")
def webhook_get(id: int | None = None, background_tasks: BackgroundTasks = None):
    """Versão GET para testes e legacy"""
    if id and background_tasks:
        db = SessionLocal()
        background_tasks.add_task(handle_mercadopago_payment, int(id), db)
    return {"ok": True}
