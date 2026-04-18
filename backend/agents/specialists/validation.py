from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
from agents.base_specialist import BaseSpecialist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationSpecialist(BaseSpecialist):
    """
    Especialista em VALIDAÇÃO (Presenter Style - 80/20):
    - Foca na coleta de dados dos acompanhantes.
    - Reconhece o hóspede principal pelo nome.
    - Transiciona para CONFIRMATION quando os dados estão completos.
    """
    
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "VALIDATION")
        self.tools = [] # No Presenter Model, o LLM não usa ferramentas

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Processa mensagem no contexto VALIDATION (Presenter Style)."""
        try:
            logger.info(f"[VALIDATION_LOG] Apresentando dados na sessão {session_id}")
            
            logic_results = logic_results or {}
            
            # Prompt dinâmico
            prompt = self._get_prompt(context)
            
            llm_messages = [SystemMessage(content=prompt)]
            if history:
                llm_messages.extend(history)
            llm_messages.append(HumanMessage(content=message))
            
            response = await self.llm.ainvoke(llm_messages)
            response_text = response.content
            
            # Transição Determinística
            next_state = 'VALIDATION'
            size = context.get('group_size', 1)
            companions = context.get('companions', [])
            
            # Se todos os acompanhantes estão preenchidos no contexto
            expected = size - 1
            is_complete = len(companions) >= expected if size > 0 else True
            
            if is_complete:
                 if any(word in response_text.lower() for word in ["concluir", "confirmar", "próximo", "continuar", "resumo", "finalizar"]):
                     next_state = 'CONFIRMATION'
            
            return {
                'response': response_text,
                'state': next_state,
                'specialist': 'validation',
                'context': context
            }
        
        except Exception as e:
            logger.error(f"[VALIDATION_LOG] Erro: {str(e)}", exc_info=True)
            return {'response': f"Erro técnico: {str(e)}", 'state': 'VALIDATION', 'specialist': 'validation', 'context': context}

    def _get_prompt(self, context: Dict[str, Any]) -> str:
        guest_name = context.get('guest_name', 'Hóspede')
        size = context.get('group_size', 1)
        expected_companions = size - 1
        companions = context.get('companions', [])
        
        status_prompt = f"""
Você é o Especialista de VALIDAÇÃO da pousada (ID: {self.tenant_id}).
Hóspede Principal: {guest_name}
Total de Pessoas: {size}
Acompanhantes Esperados: {expected_companions}
Já Coletados no sistema: {len(companions)}

MISSÃO: 
1. Coletar o Nome e a Idade de cada um dos {expected_companions} acompanhantes que faltam.
2. Seja natural e acolhedor: "Agora que te encontrei, {guest_name}, poderia me dizer quem são as outras pessoas que vão com você? Preciso apenas do nome e idade dos acompanhantes."

REGRAS CRÍTICAS:
- NUNCA peça CPF dos acompanhantes.
- NUNCA peça dados que o hóspede principal já forneceu (como o próprio nome ou documentos).
- Se já coletou tudo, convide o hóspede a ver o resumo para "Prosseguir" ou "Finalizar".
- NÃO invente nomes. Só use o que o hóspede disser.

Contexto da Sessão: {context}
"""
        return status_prompt
