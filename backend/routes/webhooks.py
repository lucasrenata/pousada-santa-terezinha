from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import hmac
import hashlib
import json
import os

from database import SessionLocal, set_tenant_context
from agents.state_manager import StateManager
import models
from agents import shared_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class MercadoPagoWebhookData(BaseModel):
    """Dados do webhook do Mercado Pago."""
    id: int
    status: str
    external_reference: Optional[str] = None
    amount: Optional[float] = None
    payer_email: Optional[str] = None

class MercadoPagoWebhook(BaseModel):
    """Payload do webhook do Mercado Pago."""
    action: str
    data: MercadoPagoWebhookData

class WebhookResponse(BaseModel):
    """Resposta padrão para webhooks."""
    success: bool
    message: str
    booking_id: Optional[int] = None
    payment_id: Optional[int] = None

# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

@router.post("/mercadopago")
async def handle_mercadopago_webhook(
    request: Request
) -> WebhookResponse:
    """
    Endpoint que recebe notificações do Mercado Pago.
    """
    db = SessionLocal()
    try:
        logger.info(f"[WEBHOOK_LOG] Recebido webhook do Mercado Pago")
        
        # 1. Validar assinatura
        signature = request.headers.get('X-Signature') or request.headers.get('x-signature')
        request_id = request.headers.get('X-Request-ID') or request.headers.get('x-request-id')
        
        if not signature or not request_id:
            logger.warning(f"[WEBHOOK_LOG] Assinatura ou Request-ID faltando")
            raise HTTPException(status_code=400, detail="Assinatura inválida")
        
        # Ler body
        body = await request.body()
        
        # Validar assinatura (HMAC-SHA256)
        if not _validate_mercadopago_signature(body, signature, request_id):
            logger.warning(f"[WEBHOOK_LOG] Assinatura inválida")
            # Note: Em produção, o MP recomenda retornar 200 até para assinaturas inválidas 
            # para evitar timing attacks ou probing, mas para debug usamos 401.
            raise HTTPException(status_code=401, detail="Assinatura inválida")
        
        logger.info(f"[WEBHOOK_LOG] Assinatura validada com sucesso")
        
        # 2. Extrair dados
        payload = json.loads(body)
        webhook = MercadoPagoWebhook(**payload)
        
        logger.info(f"[WEBHOOK_LOG] Webhook: action={webhook.action}, status={webhook.data.status}")
        
        # Ignorar ações que não são de pagamento
        if webhook.action != "payment.updated" and webhook.action != "payment.created":
            logger.info(f"[WEBHOOK_LOG] Ação ignorada: {webhook.action}")
            return WebhookResponse(success=True, message="Ação ignorada")
        
        # 3. Extrair dados de pagamento
        payment_id = webhook.data.id
        payment_status = webhook.data.status
        booking_id_str = webhook.data.external_reference
        amount = webhook.data.amount
        
        if not booking_id_str:
            logger.warning(f"[WEBHOOK_LOG] external_reference (booking_id) não encontrado")
            raise HTTPException(status_code=400, detail="booking_id não encontrado")
        
        try:
            booking_id = int(booking_id_str)
        except ValueError:
            logger.warning(f"[WEBHOOK_LOG] booking_id inválido: {booking_id_str}")
            raise HTTPException(status_code=400, detail="booking_id inválido")
        
        # 4. Buscar reserva no banco
        booking = db.query(models.Booking).get(booking_id)
        if not booking:
            logger.warning(f"[WEBHOOK_LOG] Reserva #{booking_id} não encontrada")
            raise HTTPException(status_code=404, detail="Reserva não encontrada")
        
        tenant_id = booking.tenant_id
        set_tenant_context(db, tenant_id)
        
        # 5. Processar baseado no status do pagamento
        if payment_status == "approved":
            logger.info(f"[WEBHOOK_LOG] Pagamento aprovado, atualizando reserva #{booking_id}")
            
            # Atualizar status
            booking.payment_status = models.PaymentStatus.PAGO
            booking.status = models.BookingStatus.CONFIRMADO
            booking.payment_id_mp = payment_id
            booking.payment_date = datetime.utcnow()
            
            # 6. Registrar revenue
            try:
                revenue = models.Revenue(
                    tenant_id=tenant_id,
                    description=f"Pagamento Reserva #{booking.id}",
                    amount=amount or booking.total_amount,
                    category=models.RevenueCategory.HOSPEDAGEM,
                    payment_method=models.PaymentMethod.PIX,
                    booking_id=booking.id,
                    external_payment_id=str(payment_id),
                    created_at=datetime.utcnow()
                )
                db.add(revenue)
                logger.info(f"[WEBHOOK_LOG] Revenue registrado para reserva #{booking.id}")
            except Exception as e:
                logger.error(f"[WEBHOOK_LOG] Erro ao registrar revenue: {str(e)}")
            
            db.commit()
            return WebhookResponse(success=True, message="Pagamento confirmado com sucesso", booking_id=booking_id, payment_id=payment_id)
        
        elif payment_status == "rejected" or payment_status == "cancelled":
            logger.warning(f"[WEBHOOK_LOG] Pagamento rejeitado/cancelado")
            booking.payment_status = models.PaymentStatus.CANCELADO
            db.commit()
            return WebhookResponse(success=True, message="Pagamento rejeitado", booking_id=booking_id, payment_id=payment_id)
        
        else:
            logger.info(f"[WEBHOOK_LOG] Status de pagamento {payment_status} não requer ação")
            return WebhookResponse(success=True, message=f"Status {payment_status} recebido", booking_id=booking_id, payment_id=payment_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WEBHOOK_LOG] Erro ao processar webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar webhook: {str(e)}")
    finally:
        db.close()

@router.post("/guest-registered")
async def handle_guest_registration_webhook(
    request: Request
) -> WebhookResponse:
    """
    Endpoint que recebe notificação quando hóspede se cadastra no formulário público.
    """
    try:
        logger.info(f"[WEBHOOK_LOG] Recebido webhook de cadastro de hóspede")
        payload = await request.json()
        
        tenant_id = payload.get('tenant_id')
        cpf = payload.get('cpf')
        session_id = payload.get('session_id')
        
        if not tenant_id or not cpf:
            logger.warning(f"[WEBHOOK_LOG] tenant_id ou cpf faltando")
            raise HTTPException(status_code=400, detail="tenant_id ou cpf faltando")
        
        # Usar shared_tools para processar webhook
        result = shared_tools.handle_guest_registration_webhook(
            tenant_id=tenant_id,
            cpf=cpf,
            session_id=session_id
        )
        
        if not result.get('success'):
            logger.warning(f"[WEBHOOK_LOG] Erro ao processar webhook: {result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get('error'))
        
        return WebhookResponse(success=True, message="Hóspede registrado com sucesso")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WEBHOOK_LOG] Erro ao processar webhook de cadastro: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar webhook: {str(e)}")

def _validate_mercadopago_signature(body: bytes, signature: str, request_id: str) -> bool:
    """Valida a assinatura do webhook do Mercado Pago."""
    try:
        mp_webhook_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET")
        if not mp_webhook_secret:
            logger.warning(f"[WEBHOOK_LOG] MERCADOPAGO_WEBHOOK_SECRET não configurado")
            return False
            
        data_to_sign = request_id + body.decode('utf-8')
        computed_signature = hmac.new(
            mp_webhook_secret.encode('utf-8'),
            data_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        provided_signature = signature.split('=', 1)[-1].strip() if '=' in signature else signature.strip()
        return hmac.compare_digest(computed_signature, provided_signature)
    except Exception as e:
        logger.error(f"[WEBHOOK_LOG] Erro ao validar assinatura: {str(e)}")
        return False
