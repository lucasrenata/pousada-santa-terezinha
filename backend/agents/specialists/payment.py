from typing import Dict, Any, List
from agents.base_specialist import BaseSpecialist

class PaymentSpecialist(BaseSpecialist):
    def __init__(self, tenant_id: int):
        super().__init__(tenant_id, "PAYMENT")

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None, logic_results: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "response": "Iniciando processamento de pagamento via novo motor.",
            "state": "PAYMENT",
            "specialist": "payment",
            "context": context
        }
