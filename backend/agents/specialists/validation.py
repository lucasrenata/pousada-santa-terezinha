from typing import Dict, Any, List
from agents.base_specialist import BaseSpecialist

class ValidationSpecialist(BaseSpecialist):
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "VALIDATION")

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "response": "Estamos validando seus dados. Por favor, aguarde a nova versão do motor.",
            "state": "VALIDATION",
            "specialist": "validation",
            "context": context
        }
