from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
import json
from agents.base_specialist import BaseSpecialist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfirmationSpecialist(BaseSpecialist):
    """
    Especialista em CONFIRMAÇÃO (Presenter Style - 80/20):
    - Apresenta o resumo final consolidado.
    - Pede aprovação expressa do hóspede.
    - Transiciona para PAYMENT.
    """
    
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "CONFIRMATION")
        self.tools = []

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Processa confirmação (Presenter Style)."""
        try:
            logger.info(f"[CONFIRMATION_LOG] Apresentando resumo na sessão {session_id}")
            
            logic_results = logic_results or {}
            quote = logic_results.get("quote", {})
            
            confirmation_prompt = f"""
Você é o Especialista de CONFIRMAÇÃO da pousada (ID: {self.tenant_id}).

DADOS REAIS DA RESERVA (FONTE ÚNICA):
{json.dumps(quote, ensure_ascii=False, indent=2)}

MISSÃO:
1. Apresentar o resumo da reserva de forma clara e profissional.
2. Destacar: Datas, Quartos Escolhidos, Total de Pessoas e o Valor Total.
3. Se houver uma **Opção Econômica** no contexto, reforce que esta é a escolha mais inteligente.
4. Peça uma confirmação simples: "Tudo certo com esses detalhes? Podemos gerar o link de pagamento?"

REGRAS:
- NÃO altere valores. Use exatamente o que está em 'COTAÇÃO ATUAL'.
- Seja cordial e persuasivo.

Contexto da Sessão: {json.dumps(context, ensure_ascii=False)}
"""
            
            llm_messages = [SystemMessage(content=confirmation_prompt)]
            if history:
                llm_messages.extend(history)
            llm_messages.append(HumanMessage(content=message))
            
            response = await self.llm.ainvoke(llm_messages)
            response_text = response.content
            
            # Transição Determinística
            next_state = 'CONFIRMATION'
            if any(word in response_text.lower() for word in ["pagamento", "confirmar", "gerar", "pix", "link"]):
                if any(ok in message.lower() for ok in ["sim", "pode", "ok", "confirmo", "bora"]):
                    next_state = 'PAYMENT'
            
            return {
                'response': response_text,
                'state': next_state,
                'specialist': 'confirmation',
                'context': context
            }
            
        except Exception as e:
            logger.error(f"[CONFIRMATION_LOG] Erro: {str(e)}", exc_info=True)
            return {'response': "Erro ao processar resumo. Pode repetir?", 'state': 'CONFIRMATION', 'specialist': 'confirmation', 'context': context}
