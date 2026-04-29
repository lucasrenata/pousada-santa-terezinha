from typing import Dict, Any, List, Optional
import json
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
            prompt = self._get_prompt(context, logic_results, message)
            
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

    def _get_prompt(self, context: Dict[str, Any], logic_results: Dict[str, Any] = None, message: str = "") -> str:
        logic_results = logic_results or {}
        logic_results = logic_results or {}
        guest_name = context.get('guest_name', 'Hóspede')
        size = context.get('group_size', 1)
        expected_companions = size - 1
        companions = context.get('companions', [])
        
        status_prompt = f"""
Você é o Especialista de VALIDAÇÃO da pousada (ID: {self.tenant_id}).

DADOS DO CONTEXTO (CONFIE NISSO):
Hóspede Principal: {guest_name}
Total de Pessoas no Grupo: {size}
Acompanhantes já capturados: {len(companions)}
Lista Atual: {json.dumps(companions, ensure_ascii=False)}

MUDANÇA DE IDEIA? {json.dumps(logic_results.get("intent_shift"), ensure_ascii=False)}

MISSÃO: 
1. SAUDAÇÃO PERSONALIZADA: Comece sempre usando o primeiro nome do hóspede: "{guest_name.split()[0]}".
2. RECONHECIMENTO DE MUDANÇA: Se o usuário mudou de ideia (Datas ou Pessoas), reconheça isso primeiro: "Sem problemas, {guest_name.split()[0]}, já atualizei os dados para você."
3. COLETA DE ACOMPANHANTES:
   - Se o grupo for maior que 1 ({size} > 1) e ainda faltam acompanhantes, peça educadamente o NOME e IDADE dos que faltam.
   - Se o grupo for 1 (sozinho), NÃO peça acompanhantes. Diga algo como: "Entendido! Como você estará viajando sozinho, já temos tudo o que precisamos."
4. DIRECIONAMENTO: Se já coletou todos (ou se for sozinho), convide o hóspede a ver o resumo para "Prosseguir" ou "Visualizar Resumo".

REGRAS CRÍTICAS:
- FALTAM EXATAMENTE: {max(0, expected_companions - len(companions))} acompanhantes.
- NUNCA peça CPF dos acompanhantes.
- Sua linguagem deve ser acolhedora e eficiente.

Mensagem do Hóspede: "{message}"
"""
        return status_prompt
