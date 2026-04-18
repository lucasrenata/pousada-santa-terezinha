from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class SessionState(BaseModel):
    """Modelo Pydantic para manipulação em tempo de execução via Agente"""
    user_id: Optional[str] = None
    current_step: str = 'initial'
    booking_details: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    last_query: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def current_state(self) -> str:
        return self.current_step

    def get_context(self) -> Dict[str, Any]:
        return self.model_dump()
