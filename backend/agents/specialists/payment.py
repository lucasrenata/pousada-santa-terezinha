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
            info = payment_info.get("info", {}) or payment_info
            payment_link = info.get("pix_qr", {}).get("link") if info.get("pix_qr") else None
            manual_pix = info.get("manual_key") or payment_info.get("manual_key")
            payment_method = info.get("payment_method") or payment_info.get("payment_method", "nenhum")
            total_value = info.get("total") or payment_info.get("amount", "—")
            
            payment_prompt = f"""
Você é o Especialista de PAGAMENTO da pousada (ID: {self.tenant_id}).

DADOS REAIS DO SISTEMA (NÃO INVENTE NADA):
- Link Mercado Pago disponível? {"✅ SIM" if payment_link else "❌ NÃO"}
- Chave PIX Manual cadastrada? {"✅ SIM → " + str(manual_pix) if manual_pix else "❌ NÃO CADASTRADA"}
- Valor total: R$ {total_value}
- Status da Reserva: {booking_status}

MISSÃO (SIGA ESTA ORDEM EXATA):

CASO 1 — Link do Mercado Pago DISPONÍVEL:
  → Apresente o link clicável: [**Clique aqui para pagar agora**]({payment_link})
  → Informe o valor e incentive o hóspede a finalizar para garantir a vaga.
  → Após apresentar o link, informe: "Se tiver dificuldade com o link, entre em contato conosco."

CASO 2 — Link do Mercado Pago NÃO DISPONÍVEL, mas Chave PIX cadastrada:
  → Diga: "No momento o pagamento online (Mercado Pago) está indisponível, mas você pode finalizar sua reserva via PIX direto."
  → Forneça a chave PIX de forma destacada: **Chave PIX: {manual_pix if manual_pix else "não disponível"}**
  → INSTRUÇÃO OBRIGATÓRIA: Peça ao hóspede para enviar o comprovante de pagamento aqui mesmo no chat assim que concluir.
  → AVISO DE EXPIRAÇÃO: Informe que a reserva ficará garantida com status **PENDENTE por no máximo 2 horas**. Caso o comprovante não seja enviado neste prazo, o quarto será liberado automaticamente para outros interessados.
  → Explique: "Assim que você enviar o comprovante, faremos a validação manual e sua reserva será confirmada imediatamente."

CASO 3 — Nenhuma forma de pagamento disponível:
  → Diga: "No momento estamos sem sistema de pagamento online. Por favor, entre em contato diretamente com a pousada para concluir sua reserva."

CASO 4 — Reserva CONFIRMADA ou ATIVA:
  → Celebre: "Tudo certo! Sua reserva está confirmada. Esperamos por você! 🎉"

REGRAS CRÍTICAS:
- NUNCA invente um link ou chave PIX. Se não há dados, use o CASO 3.
- NUNCA diga "aguarde o sistema gerar o link".
- Formate valores em R$ 0,00.
- Seja proativo, amigável e objetivo.
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
