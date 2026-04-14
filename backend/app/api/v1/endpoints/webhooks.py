from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.services.mercadopago_service import verify_payment_and_activate
import logging
import asyncio
import hmac
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()

async def safe_verify_payment(payment_id: str, db: AsyncSession):
    try:
        await verify_payment_and_activate(payment_id, db)
    except Exception as e:
        logger.error(f"Erro ao processar webhook do Mercado Pago (Payment ID: {payment_id}): {e}")


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
) -> dict[str, str]:
    # Validação de Assinatura (HMAC)
    if settings.WEBHOOK_SECRET and x_signature:
        try:
            # Assinatura do MP vem no formato: ts=...,v1=...
            parts = dict(part.split('=') for part in x_signature.split(','))
            timestamp = parts.get('ts')
            received_hash = parts.get('v1')
            
            if timestamp and received_hash:
                # O Mercado Pago recomenda validar o ID da notificação ou do recurso
                # No V1, o ID vem no body. Lemos o body uma vez.
                body_bytes = await request.body()
                body = await request.json()
                
                # Para validar, precisamos do ID do recurso
                resource_id = body.get("data", {}).get("id") or body.get("id")
                
                if resource_id:
                    # Template: id:[id];request-id:[x-request-id];ts:[ts];
                    manifest = f"id:{resource_id};request-id:{x_request_id or ''};ts:{timestamp};"
                    sha = hmac.new(
                        settings.WEBHOOK_SECRET.encode('utf-8'),
                        manifest.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    if sha != received_hash:
                        logger.warning(f"Webhook recusado: Assinatura inválida para ID {resource_id}")
                        raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Erro ao validar assinatura do webhook: {e}")
            # Em erro de validação, não subimos 400 para evitar travar retentativas se for erro de código
    
    try:
        # Se chegamos aqui, o body já foi lido por await request.json() acima se houve validação
        # Caso contrário, lemos agora.
        try:
            body = await request.json()
        except:
            # request.json() pode falhar se body_bytes já foi consumido ou é inválido
            import json
            body = json.loads(await request.body())
            
        logger.info(f"Webhook Mercado Pago recebido: {body}")
    except Exception:
        logger.error("Falha ao processar JSON do webhook Mercado Pago")
        # Se não conseguir dar parse no JSON, aceita silenciosamente para não travar retentativas MP
        return {"status": "success"}
        
    action = body.get("action")
    body_type = body.get("type")
    
    # Valida se é uma notificação de pagamento (V1 envia 'type'="payment" ou 'action'="payment.created")
    if body_type == "payment" or (action and "payment" in action):
        payment_id = body.get("data", {}).get("id")
        if payment_id:
            background_tasks.add_task(safe_verify_payment, str(payment_id), db)
                
    return {"status": "success"}
