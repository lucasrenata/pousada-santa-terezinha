from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
import json
from agents.base_specialist import BaseSpecialist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentSpecialist(BaseSpecialist):
    """
    Especialista em PAGAMENTO (Presenter Style - 80/20):
    - Fornece link ou QR Code PIX.
    - Monitora o status de pagamento via logic_results (MP Webhook).
    - Encoraja o hóspede e finaliza o atendimento após confirmação.
    """
    
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "PAYMENT")
        self.tools = []

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Processa pagamento (Presenter Style)."""
        try:
            logger.info(f"[PAYMENT_LOG] Gerenciando pagamento na sessão {session_id}")
            
            logic_results = logic_results or {}
            payment_info = logic_results.get("payment", {})
            booking_status = logic_results.get("booking_status", "PENDENTE")
            
            # Extração robusta do link de pagamento (Padrão 80/20)
            info = payment_info.get("info", {})
            payment_link = info.get("pix_qr", {}).get("link")
            manual_pix = payment_info.get("manual_key") or info.get("manual_key")
            
            payment_prompt = f"""
Você é o Especialista de PAGAMENTO da pousada (ID: {self.tenant_id}).

INFORMAÇÕES DE PAGAMENTO (REAIS):
{json.dumps(payment_info, ensure_ascii=False, indent=2)}

DADOS PARA O HÓSPEDE:
- Link Mercado Pago: {payment_link if payment_link else "NÃO DISPONÍVEL"}
- Chave PIX Manual: {manual_pix if manual_pix else "NÃO CADASTRADA"}
- Status Reserva: {booking_status}

MISSÃO:
1. Se o status for PENDENTE: Proporcione IMEDIATAMENTE uma forma de pagamento.
   - SE houver Link Mercado Pago: Use [**Pagar Agora**]({payment_link}).
   - SE NÃO houver link, mas houver Chave PIX: Forneça a chave {manual_pix} e peça para enviar o comprovante aqui.
   - SEMPRE incentive o hóspede a concluir agora para garantir a vaga.
2. Se o status for CONFIRMADO: Celebre com o hóspede e confirme que está tudo certo.

REGRAS CRÍTICAS:
- NUNCA peça para o hóspede "aguardar o sistema gerar o link". Se não tem link, use a chave PIX manual.
- Formate valores em R$ 0,00.
- Seja extremamente proativo e amigável.
"""
            
            llm_messages = [SystemMessage(content=payment_prompt)]
            if history:
                llm_messages.extend(history)
            llm_messages.append(HumanMessage(content=message))
            
            response = await self.llm.ainvoke(llm_messages)
            response_text = response.content
            
            # Estado final: Se confirmado, encerra o fluxo principal
            next_state = 'PAYMENT'
            if booking_status in ["CONFIRMADO", "ATIVO"]:
                next_state = 'DISCOVERY' # Volta para o início para novos atendimentos
            
            return {
                'response': response_text,
                'state': next_state,
                'specialist': 'payment',
                'context': context
            }
            
        except Exception as e:
            logger.error(f"[PAYMENT_LOG] Erro: {str(e)}", exc_info=True)
            return {'response': "Estou verificando seu pagamento, um momento...", 'state': 'PAYMENT', 'specialist': 'payment', 'context': context}
