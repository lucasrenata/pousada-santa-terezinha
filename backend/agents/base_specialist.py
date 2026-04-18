from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import logging
import os

from agents.state_manager import StateManager
from database import SessionLocal, set_tenant_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseSpecialist:
    """
    Classe base para todos os especialistas.
    
    PRINCÍPIOS:
    1. Nunca recebe db_session no __init__ (instancia seu próprio StateManager)
    2. Abre/fecha sessão para cada operação de negócio que não seja via StateManager
    3. Trabalha com dados puros (int, str, list)
    4. StateManager gerencia todo o estado de forma isolada
    """
    
    def __init__(self, tenant_id: int, specialist_name: str):
        self.tenant_id = tenant_id
        self.specialist_name = specialist_name
        self.state_manager = StateManager(tenant_id)
        
        # Inicializar LLM (com fallback seguro para gemini-2.5-flash-lite)
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=google_key,
                temperature=0.1
            )
            logger.info(f"[{self.specialist_name}_LOG] Usando Gemini: {model_name}")
        else:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.2
            )
            logger.info(f"[{self.specialist_name}_LOG] Usando OpenAI GPT-4o Mini")
        
        self.llm_with_tools = None  # Será definido em subclasses
    
    def _get_db_session(self) -> Session:
        """
        Abre uma nova sessão de banco de dados isolada.
        IMPORTANTE: Deve ser fechada com db.close() após uso.
        """
        db = SessionLocal()
        set_tenant_context(db, self.tenant_id)
        return db

    async def process(self, message: str, session_id: str, context: Dict[str, Any], history: List[Any] = None) -> Dict[str, Any]:
        """
        Contrato de processamento principal.
        
        Args:
            message: Texto atual do usuário.
            session_id: ID da sessão para rastreamento.
            context: Dicionário de fatos extraídos até agora.
            history: Lista de mensagens anteriores (BaseMessage).
        """
        raise NotImplementedError("Subclasses devem implementar process()")
    
    def _load_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        Carrega contexto da sessão via StateManager.
        Retorna dados puros (nunca objetos ORM).
        """
        session_data = self.state_manager.load_session(session_id)
        if not session_data:
            return {}
        return session_data.get('context', {})
    
    def _save_session_state(self, session_id: str, new_state: str, context_update: Dict[str, Any]) -> bool:
        """
        Salva estado da sessão via StateManager.
        Delegado ao SupervisorAgent na arquitetura de Concatenação de Memória.
        """
        updates = {**context_update, 'current_state': new_state}
        result = self.state_manager.update_state(session_id, updates)
        return result.get('success', False)
    
    def _get_guest_id_from_context(self, context: Dict[str, Any]) -> Optional[int]:
        """Extrai guest_id do contexto de forma segura."""
        guest_id = context.get('guest_id')
        if guest_id is None: return None
        try: return int(guest_id)
        except (ValueError, TypeError): return None
    
    def _get_booking_id_from_context(self, context: Dict[str, Any]) -> Optional[int]:
        """Extrai booking_id do contexto de forma segura."""
        booking_id = context.get('booking_id')
        if booking_id is None: return None
        try: return int(booking_id)
        except (ValueError, TypeError): return None
