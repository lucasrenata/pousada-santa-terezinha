import os
import logging
import asyncio
from google import genai
from google.genai import types
from database import SessionLocal, set_tenant_context
import models

logger = logging.getLogger(__name__)

class AuditorAgent:
    """
    Agente de Auditoria (QA) usando Gemini 2.0 Flash Lite.
    Sua missão é verificar se as ações realizadas pelas ferramentas (reservas, pagamentos)
    realmente persistiram no banco de dados antes da IA confirmar ao usuário.
    """
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash-lite"

    async def verify_action(self, action_type: str, action_details: dict) -> bool:
        """
        Verifica se uma ação foi executada com sucesso no mundo real (BD).
        Retorna True se confirmado, False se falhou.
        """
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            
            if action_type == "create_booking":
                booking_id = action_details.get("booking_id")
                if not booking_id: return False
                
                # Verifica se a reserva existe e tem os dados básicos
                booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
                if not booking:
                    logger.error(f"🚨 [AUDITOR] Falha Crítica: Reserva {booking_id} não encontrada no banco!")
                    return False
                
                # Verifica integridade (ex: se tem quartos associados)
                if not booking.room_associations or not booking.total_amount:
                    logger.error(f"🚨 [AUDITOR] Falha de Integridade: Reserva {booking_id} incompleta (quartos ou valor ausentes).")
                    return False
                
                logger.info(f"✅ [AUDITOR] Reserva {booking_id} verificada com sucesso.")
                return True

            elif action_type == "identify_guest":
                guest_id = action_details.get("guest_id")
                guest = db.query(models.Guest).filter(models.Guest.id == guest_id).first()
                return guest is not None

            # Outras verificações podem ser adicionadas aqui
            return True
            
        except Exception as e:
            logger.error(f"❌ [AUDITOR] Erro durante verificação: {e}")
            return False
        finally:
            db.close()

    async def audit_response(self, ai_text: str, context: dict) -> str:
        """
        Analisa a resposta que a IA pretende dar e decide se é segura.
        Se a IA disser 'Reserva criada' mas a verificação falhou, o Auditor corrige.
        """
        # Se a IA está confirmando algo que falhou na verificação
        if "sucesso" in ai_text.lower() or "confirmad" in ai_text.lower() or "criada" in ai_text.lower():
            is_valid = await self.verify_action(context.get("last_action"), context.get("action_details", {}))
            
            if not is_valid:
                logger.warning(f"⚠️ [AUDITOR] Bloqueando resposta falsa de sucesso. Corrigindo...")
                return "Peço mil desculpas, mas parece que houve um pequeno erro técnico ao finalizar sua solicitação no sistema. Poderia confirmar os dados novamente para que eu tente processar mais uma vez?"
        
        return ai_text
