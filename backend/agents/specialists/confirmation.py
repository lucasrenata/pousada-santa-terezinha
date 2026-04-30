from typing import Dict, Any, List
from agents.base_specialist import BaseSpecialist

class ConfirmationSpecialist(BaseSpecialist):
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "CONFIRMATION")

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "response": "Aguardando confirmação final no novo motor.",
            "state": "CONFIRMATION",
            "specialist": "confirmation",
            "context": context
        }
