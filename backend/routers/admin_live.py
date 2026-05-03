from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import logging
from app.services.gemini_live_service import gemini_live_service
from database import get_db
from sqlalchemy.orm import Session
import models

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin Live"])

@router.websocket("/ws/admin/live/{tenant_id}")
async def admin_live_ws(websocket: WebSocket, tenant_id: int):
    """
    Endpoint WebSocket para a conversa voz a voz com a assistente holográfica.
    """
    await websocket.accept()
    logger.info(f"Nova conexão WebSocket Admin Live para tenant {tenant_id}")
    
    try:
        # Proxy para o Gemini Live API
        await gemini_live_service.connect_and_proxy(websocket, tenant_id)
    except WebSocketDisconnect:
        logger.info(f"Conexão WebSocket Admin Live encerrada para tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Erro na conexão WebSocket Admin Live: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
