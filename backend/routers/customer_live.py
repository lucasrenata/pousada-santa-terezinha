import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.customer_live_service import CustomerLiveService

router = APIRouter(tags=["Customer Voice"])
logger = logging.getLogger("routers.customer_live")

# Instância única do serviço
live_service = CustomerLiveService()

@router.websocket("/ws/customer/live/{tenant_id}")
async def customer_live_ws(websocket: WebSocket, tenant_id: int, session_id: str = "guest_default"):
    """
    Endpoint WebSocket para atendimento por voz ao HÓSPEDE (Gemini Live).
    """
    await websocket.accept()
    logger.info(f"Nova conexão WebSocket Customer Live para tenant {tenant_id} (Session: {session_id})")
    
    try:
        # Inicia a ponte com o Gemini Live
        await live_service.connect_and_proxy(tenant_id, session_id, websocket)
    except WebSocketDisconnect:
        logger.info(f"Conexão Customer Live encerrada pelo cliente (tenant {tenant_id})")
    except Exception as e:
        logger.error(f"Erro crítico no WebSocket Customer Live (tenant {tenant_id}): {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except:
            pass
