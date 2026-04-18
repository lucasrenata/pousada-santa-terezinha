import unittest
import sys
import os

# Adiciona o diretório backend ao path para os imports funcionarem no teste local
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal, set_tenant_context
from agents.state_manager import StateManager
from agents.schemas.session_state import SessionState

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.tenant_id = 1 # Tenant de teste
        
        # ESSENCIAL para a Arquitetura de Tenants:
        # Define o contexto da sessão para o banco permitir o acesso via RLS
        set_tenant_context(self.db, self.tenant_id)
        
        self.manager = StateManager(self.db, self.tenant_id)
        self.session_id = 'test_session_123'

    def tearDown(self):
        # Limpa o estado de teste
        from models import SessionState as SessionStateDB
        self.db.query(SessionStateDB).filter(SessionStateDB.session_id == self.session_id).delete()
        self.db.commit()
        self.db.close()

    def test_get_state_initial(self):
        """Novo registro deve vir com estado initial"""
        state = self.manager.get_state(self.session_id)
        self.assertIsInstance(state, SessionState)
        self.assertEqual(state.current_step, 'initial')

    def test_update_state_persistence(self):
        """Atualização deve persistir no banco e ser recuperável"""
        updates = {'current_step': 'booking', 'user_id': 'guest_001'}
        self.manager.update_state(self.session_id, updates)
        
        # Recupera novamente para validar persistência
        new_state = self.manager.get_state(self.session_id)
        self.assertEqual(new_state.current_step, 'booking')
        self.assertEqual(new_state.user_id, 'guest_001')

    def test_tenant_isolation(self):
        """Sessão de um tenant não deve ser visível para outro"""
        self.manager.update_state(self.session_id, {'current_step': 'secret_state'})
        
        # Cria manager para outro tenant
        other_manager = StateManager(self.db, tenant_id=2)
        other_state = other_manager.get_state(self.session_id)
        
        self.assertEqual(other_state.current_step, 'initial') # Não deve ver o 'secret_state' do tenant 1

if __name__ == '__main__':
    unittest.main()
