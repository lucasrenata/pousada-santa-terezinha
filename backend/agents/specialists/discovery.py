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

            # O Guardian escreve os dados no context, mas o logic_node pode atualizá-los
            # Por isso consultamos as duas fontes para ter certeza
            updated_ctx = logic_results.get("updated_context", {})
            check_in  = context.get("check_in")  or updated_ctx.get("check_in")
            check_out = context.get("check_out") or updated_ctx.get("check_out")
            group_size = context.get("group_size") or updated_ctx.get("group_size")
            guest_found = logic_results.get("guest", {}).get("found", False)
            guest_name  = updated_ctx.get("guest_name") or context.get("guest_name", "")

            discovery_prompt = f"""
Você é o Especialista de Atendimento da pousada (ID: {self.tenant_id}).
Hoje é {today_str}.

═══════════════════════════════════════════════════════
ESTADO REAL DO ATENDIMENTO (FONTE ÚNICA E DEFINITIVA):
═══════════════════════════════════════════════════════
- Hóspede identificado? {"✅ SIM — " + guest_name if guest_found else "❌ NÃO"}
- Check-in fornecido?   {"✅ " + str(check_in) if check_in else "❌ NÃO"}
- Check-out fornecido?  {"✅ " + str(check_out) if check_out else "❌ NÃO"}
- Nº de pessoas?        {"✅ " + str(group_size) if group_size else "❌ NÃO"}
- Opções de quartos:    {json.dumps(availability, ensure_ascii=False)}
- Cotação:              {json.dumps(quote, ensure_ascii=False)}

DIRETRIZES (SIGA NESTA ORDEM EXATA):

PASSO 1 — CPF faltando → Peça o CPF de forma cordial para localizar o cadastro. Pare aqui.

PASSO 2 — CPF ok, Hóspede identificado (✅), mas check-in/check-out/pessoas FALTANDO:
   → Comece com: "Olá {guest_name.split()[0]}! Encontrei seu cadastro aqui." (ou similar)
   → Em seguida, peça as informações faltantes: "Para quando você deseja a reserva e para quantas pessoas?"
   → REGRA DE OURO: Se as datas já estão marcadas com ✅ acima, você está PROIBIDO de perguntar por elas.

PASSO 3 — CPF ok, Hóspede identificado (✅), datas e pessoas PRESENTES (✅):
   → Saudação inicial (se ainda não feita): "Olá {guest_name.split()[0]}!"
   → NÃO repita a pergunta de datas. Elas já foram informadas.
   → SE há quartos disponíveis: Apresente as opções com preços e convide-o a escolher.
   → SE não há quartos: Informe educadamente que não há disponibilidade para essas datas e sugira outras datas próximas.

PASSO 4 — Quarto escolhido e dados completos:
   → Confirme a escolha e convide para o resumo para finalizar.

REGRAS DE OURO:
- NUNCA pergunte algo que já está marcado com ✅.
- SEMPRE use o nome do hóspede {guest_name.split()[0]} se ele estiver identificado (✅). 
- Se não houver quartos, NÃO pergunte as datas de novo. Apenas informe o hóspede.

Contexto completo da sessão: {json.dumps({**context, **updated_ctx}, ensure_ascii=False)}
"""
            
            llm_messages = [SystemMessage(content=discovery_prompt)]
            if history:
                llm_messages.extend(history)
            
            # Reforço final: injeta o estado atual logo antes da mensagem do usuário
            reinforcement = f"""[INSTRUÇÃO DO SISTEMA — PRIORIDADE MÁXIMA]
ESTADO ATUAL:
- check_in disponível? {"SIM: " + str(check_in) if check_in else "NÃO"}
- check_out disponível? {"SIM: " + str(check_out) if check_out else "NÃO"}
- Hóspede identificado? {"SIM: " + str(guest_name) if guest_found else "NÃO"}

Se datas e pessoas estão disponiveis (SIM): Fale sobre os QUARTOS disponíveis ou avise sobre a LOTAÇÃO. É PROIBIDO perguntar "Para quando?" se já temos as datas acima.
"""
            llm_messages.append(SystemMessage(content=reinforcement))
            llm_messages.append(HumanMessage(content=message))
            
            # Chamada direta ao LLM (sem ferramentas)
            response = await self.llm.ainvoke(llm_messages)
            response_text = response.content
            
            # Inteligência de Transição (DETERMINÍSTICA + TEXTUAL)
            next_state = "DISCOVERY"
            
            # Se já temos os dados básicos, permitimos o avanço emocional para VALIDATION
            has_basic_data = bool(check_in and check_out and group_size)
            
            if has_basic_data:
                # Se o usuário escolheu um quarto ou a IA sugeriu avançar
                triggered_by_text = any(word in response_text.lower() for word in ["prosseguir", "finalizar", "confirmar", "acompanhante", "resumo", "validar"])
                has_room = bool(context.get('room_id') or updated_ctx.get('room_id'))
                
                if triggered_by_text or has_room:
                    next_state = "VALIDATION"
                # Se temos os dados mas a IA lotou ou errou, mantemos em DISCOVERY para ela se corrigir
                # mas abrimos a porta para o Supervisor forçar se necessário.

            return {
                'response': response_text,
                'state': next_state,
                'specialist': 'discovery',
                'context': context
            }
        
        except Exception as e:
            logger.error(f"[DISCOVERY_LOG] Erro: {str(e)}", exc_info=True)
            return {'response': "Desculpe, tive um problema técnico. Pode repetir?", 'state': 'DISCOVERY', 'specialist': 'discovery', 'context': context}
