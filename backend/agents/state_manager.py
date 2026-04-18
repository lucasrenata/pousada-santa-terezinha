from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date
import logging
import json

from database import SessionLocal, set_tenant_context
import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StateManager:
    """
    Gerenciador de estado de sessão com suporte nativo a Multi-Tenancy e UPSERT atômico.
    """
    
    _instances = {}

    def __new__(cls, tenant_id: int):
        if tenant_id not in cls._instances:
            cls._instances[tenant_id] = super(StateManager, cls).__new__(cls)
        return cls._instances[tenant_id]

    def __init__(self, tenant_id: int):
        if not hasattr(self, 'initialized'):
            self.tenant_id = tenant_id
            self.initialized = True
            logger.info(f"[STATE_LOG] StateManager inicializado para tenant {tenant_id}")
    
    def create_session(self, session_id: str, initial_context: Dict[str, Any] = None) -> dict:
        """
        Cria ou Sincroniza uma sessão de estado usando UPSERT atômico.
        Imune a erros de UniqueViolation causados por isolamento RLS.
        """
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            
            context = initial_context or {}
            context = self._sanitize_context(context)
            context_str = json.dumps(context)
            
            stmt = text("""
                INSERT INTO session_state (session_id, current_state, context_json, tenant_id, created_at, updated_at)
                VALUES (:sid, :state, :context, :tid, :now, :now)
                ON CONFLICT (session_id) DO UPDATE SET
                    context_json = EXCLUDED.context_json,
                    current_state = EXCLUDED.current_state,
                    updated_at = EXCLUDED.updated_at,
                    tenant_id = EXCLUDED.tenant_id
            """)
            
            now = datetime.utcnow()
            db.execute(stmt, {
                "sid": session_id,
                "state": context.get('current_state', 'DISCOVERY'),
                "context": context_str,
                "tid": self.tenant_id,
                "now": now
            })
            db.commit()
            
            logger.info(f"[STATE_LOG] Sessão sincronizada (UPSERT): {session_id}")
            return {'success': True}
        
        except Exception as e:
            db.rollback()
            logger.error(f"[STATE_LOG] Erro ao sincronizar sessão {session_id}: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega estado com isolamento garantido.
        """
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            
            session_state = db.query(models.SessionState).filter(
                models.SessionState.session_id == session_id,
                models.SessionState.tenant_id == self.tenant_id
            ).first()
            
            if not session_state:
                logger.warning(f"[STATE_LOG] Sessão {session_id} não encontrada para tenant {self.tenant_id}")
                return None
            
            return {
                'session_id': session_state.session_id,
                'current_state': session_state.current_state,
                'context': json.loads(session_state.context_json) if session_state.context_json else {},
                'created_at': session_state.created_at.isoformat() if session_state.created_at else None,
                'updated_at': session_state.updated_at.isoformat() if session_state.updated_at else None
            }
        except Exception as e:
            logger.error(f"[STATE_LOG] Erro ao carregar sessão {session_id}: {str(e)}")
            return None
        finally:
            db.close()

    def get_state(self, session_id: str):
        """Compatibilidade com SupervisorAgent."""
        session = self.load_session(session_id)
        from agents.schemas.session_state import SessionState
        if not session:
            return SessionState()
        return SessionState(**session['context'])

    def update_state(self, session_id: str, updates: Dict[str, Any]) -> dict:
        """
        Atualiza estado de forma resiliente.
        """
        db = SessionLocal()
        try:
            set_tenant_context(db, self.tenant_id)
            
            session_state = db.query(models.SessionState).filter(
                models.SessionState.session_id == session_id,
                models.SessionState.tenant_id == self.tenant_id
            ).first()
            
            if not session_state:
                logger.info(f"[STATE_LOG] Sessão {session_id} nova ou oculta, usando create_session (UPSERT)")
                return self.create_session(session_id, updates)

            current_context = json.loads(session_state.context_json) if session_state.context_json else {}
            new_state = updates.pop('current_state', session_state.current_state)
            
            context_update = self._sanitize_context(updates)
            
            # Fusão blindada
            for key, val in context_update.items():
                if val is not None and (val != "" and val != [] and val != {}):
                    current_context[key] = val
            
            session_state.current_state = new_state
            session_state.context_json = json.dumps(current_context)
            session_state.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"[STATE_LOG] Estado atualizado: {session_id} -> {new_state}")
            return {'success': True, 'context': current_context}
        
        except Exception as e:
            db.rollback()
            logger.error(f"[STATE_LOG] Falha no update {session_id}: {str(e)}. Fallback para UPSERT.")
            return self.create_session(session_id, updates)
        finally:
            db.close()
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        session = self.load_session(session_id)
        return session.get('context', {}) if session else {}
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in context.items():
            if v is None: continue
            sanitized[k] = self._sanitize_val(v)
        return sanitized

    def _sanitize_val(self, val: Any) -> Any:
        if val is None or isinstance(val, (int, str, float, bool)):
            return val
        if isinstance(val, (date, datetime)):
            return val.isoformat()
        if isinstance(val, dict):
            return {k: self._sanitize_val(v) for k, v in val.items()}
        if isinstance(val, list):
            return [self._sanitize_val(v) for v in val]
        try:
            return str(val)
        except:
            return None
