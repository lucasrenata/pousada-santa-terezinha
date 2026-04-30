from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_specialist import BaseSpecialist

class DiscoverySpecialist(BaseSpecialist):
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "DISCOVERY")

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        instruction = logic_results.get("engine_instruction", "Como posso ajudar?")
        reg_link = context.get("registration_link", "")
        guest_name = context.get("guest_name", "Hóspede")
        guest_found = context.get("guest_found", False)

        prompt = f"""
Você é a recepção da pousada. Seu tom é cordial e prestativo.
OBEDEÇA ESTA INSTRUÇÃO DO MOTOR: "{instruction}"

DADOS DO SISTEMA:
- Hóspede encontrado? {"SIM - " + guest_name if guest_found else "NÃO"}
- Link de Cadastro: {reg_link}

REGRAS:
1. Se o hóspede não for encontrado, entregue o link de cadastro IMEDIATAMENTE.
2. Seja breve e acolhedor.
3. Não invente nenhuma informação.
"""
        messages = [SystemMessage(content=prompt)]
        if history: messages.extend(history)
        messages.append(HumanMessage(content=message))
        
        response = await self.llm.ainvoke(messages)
        
        return {
            "response": response.content,
            "state": logic_results.get("engine_state", "DISCOVERY"),
            "specialist": "discovery",
            "context": context
        }
