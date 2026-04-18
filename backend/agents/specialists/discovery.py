from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import logging
import json
from datetime import datetime
from agents.base_specialist import BaseSpecialist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscoverySpecialist(BaseSpecialist):
    """
    Especialista em APRESENTAÇÃO (80/20 Architecture):
    - Recebe dados determinísticos do Nó de Lógica.
    - Foca em comunicação cordial e persuasão de vendas.
    """
    
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "DISCOVERY")
        # No 80/20, a IA não chama ferramentas. O código Python já as chamou.
        self.tools = [] 

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            logger.info(f"[DISCOVERY_LOG] Apresentando dados na sessão {session_id}")
            
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d (%A)")
            
            # Extrair dados "carimbados" pelo código
            logic_results = logic_results or {}
            availability = logic_results.get("availability", {})
            quote = logic_results.get("quote", {})
            payment = logic_results.get("payment", {})

            discovery_prompt = f"""
Você é o Especialista de Atendimento da pousada (ID: {self.tenant_id}).
Hoje é {today_str}.

SUA MISSÃO: Atender o hóspede de forma amigável, seguindo o protocolo de segurança.

DADOS REAIS DO SISTEMA (FONTE ÚNICA DA VERDADE):
- DISPONIBILIDADE: {json.dumps(availability, ensure_ascii=False)}
- COTAÇÃO ATUAL: {json.dumps(quote, ensure_ascii=False)}
- INFORMAÇÃO DE PAGAMENTO: {json.dumps(payment, ensure_ascii=False)}
- BUSCA DE HÓSPEDE: {json.dumps(logic_results.get("guest", {}), ensure_ascii=False)}

STATUS ATUAL DO ATENDIMENTO:
- CPF Capturado? {"SIM" if context.get("cpf") else "NÃO"}
- Cadastro Localizado? {"SIM" if logic_results.get("guest", {}).get("found") else "NÃO"}
- Dados do Cadastro: {json.dumps(logic_results.get("guest", {}), ensure_ascii=False)}

DIRETRIZES DE RESPOSTA (MACRO FLOW):

1. IDENTIFICAÇÃO (PORTARIA):
   - Se CPF estiver FALTANDO: Diga: "Seja bem-vindo! Para iniciarmos seu atendimento, por favor me informe o seu CPF para que eu possa localizar seu cadastro."
   - SEMPRE espere o CPF antes de oferecer opções de quartos ou preços.

2. RECONHECIMENTO (SE CPF PRESENTE):
   - Se 'Cadastro Localizado' for SIM: Diga: "Olá, [Nome do Cadastro]! Encontrei você aqui no sistema. Que bom ter você conosco. Para quando você deseja a reserva e para quantas pessoas?"
   - Se 'Cadastro Localizado' for NÃO: Diga educadamente: "Não localizei seu cadastro com este CPF. Para podermos concluir, por favor preencha seus dados neste link: [**Clique aqui para se cadastrar**]({logic_results.get('guest', {}).get('registration_link')})"

3. DISPONIBILIDADE E PREÇOS:
   - Somente após o hóspede ser identificado e fornecer datas/pessoas, apresente as opções de {json.dumps(availability, ensure_ascii=False)} e {json.dumps(quote, ensure_ascii=False)}.
   - Priorize sempre a **Opção Econômica** (Smart Split) se o hóspede pedir economia ou se for mais barato que um único quarto.

4. PROIBIÇÃO DE SERVIÇOS EXTRAS:
   - NUNCA ofereça serviços como café da manhã, estacionamento ou check-out tardio a menos que listados nos DADOS REAIS.

Responda de forma natural, mas siga estas regras na ordem exata.

Contexto da Sessão: {json.dumps(context, ensure_ascii=False)}

Responda de forma natural e humana.
"""
            
            llm_messages = [SystemMessage(content=discovery_prompt)]
            if history:
                llm_messages.extend(history)
            llm_messages.append(HumanMessage(content=message))
            
            # Chamada direta ao LLM (sem ferramentas)
            response = await self.llm.ainvoke(llm_messages)
            response_text = response.content
            
            # Inteligência de Transição (Mantida p/ controle do Grafo)
            next_state = "DISCOVERY"
            if context.get('check_in') and context.get('check_out') and context.get('room_id'):
                 if any(word in response_text.lower() for word in ["cpf", "prosseguir", "finalizar", "confirmar"]):
                     next_state = "VALIDATION"

            return {
                'response': response_text,
                'state': next_state,
                'specialist': 'discovery',
                'context': context
            }
        
        except Exception as e:
            logger.error(f"[DISCOVERY_LOG] Erro: {str(e)}", exc_info=True)
            return {'response': "Desculpe, tive um problema técnico. Pode repetir?", 'state': 'DISCOVERY', 'specialist': 'discovery', 'context': context}
