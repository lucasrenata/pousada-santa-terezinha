import unittest
import asyncio
from unittest.mock import Mock, patch
from agents.state_manager import StateManager
from agents.base_specialist import BaseSpecialist

class TestStateManagerIsolation(unittest.TestCase):
    """Testa isolamento de sessão do StateManager (Resilience Layer)."""
    
    def test_singleton_per_tenant(self):
        """Testa se o StateManager é singleton por tenant_id."""
        sm1 = StateManager(tenant_id=1)
        sm2 = StateManager(tenant_id=1)
        sm3 = StateManager(tenant_id=2)
        
        self.assertIs(sm1, sm2)
        self.assertIsNot(sm1, sm3)
    
    def test_create_session_isolates_connection(self):
        """Testa que create_session funciona sem erro de transação."""
        state_mgr = StateManager(tenant_id=1)
        session_id = f"test_resilience_{id(state_mgr)}"
        
        result = state_mgr.create_session(
            session_id,
            {'guest_id': 123, 'guest_name': 'João Teste'}
        )
        
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('session_id'), session_id)
    
    def test_load_session_returns_pure_data(self):
        """Testa que load_session retorna dados puros (não ORM)."""
        state_mgr = StateManager(tenant_id=1)
        session_id = "test_data_purity"
        
        state_mgr.create_session(session_id, {'guest_id': 456})
        session_data = state_mgr.load_session(session_id)
        
        self.assertIsNotNone(session_data)
        self.assertIsInstance(session_data['context'], dict)
        self.assertEqual(session_data['context']['guest_id'], 456)
    
    def test_sanitize_context(self):
        """Testa que _sanitize_context remove objetos complexos."""
        state_mgr = StateManager(tenant_id=1)
        
        class FakeORM: pass
        
        context = {
            'id': 1,
            'name': 'Teste',
            'orm': FakeORM(), # Deve ser removido ou processado com segurança
            'meta': {'deep': True}
        }
        
        sanitized = state_mgr._sanitize_context(context)
        self.assertEqual(sanitized['id'], 1)
        self.assertEqual(sanitized['name'], 'Teste')
        self.assertEqual(sanitized['meta']['deep'], True)
        # O sanitizador atual tenta converter para str se for desconhecido
        self.assertIsInstance(sanitized['orm'], str)
    
    def test_update_state_concurrency_safe(self):
        """Testa que update_state funciona sem invalidar o objeto."""
        state_mgr = StateManager(tenant_id=1)
        session_id = "test_update_safe"
        
        state_mgr.create_session(session_id, {'stage': 'start'})
        
        # Atualização 1
        state_mgr.update_state(session_id, {'current_state': 'VALIDATION', 'field': 1})
        # Atualização 2 (IMEDIATA)
        state_mgr.update_state(session_id, {'field': 2})
        
        session = state_mgr.load_session(session_id)
        self.assertEqual(session['current_state'], 'VALIDATION')
        self.assertEqual(session['context']['field'], 2)

class TestBaseSpecialistPattern(unittest.TestCase):
    """Testa padrão seguro de BaseSpecialist."""
    
    def test_base_specialist_initialization(self):
        """Testa inicialização sem db_session externa."""
        specialist = BaseSpecialist(tenant_id=1, specialist_name="TEST")
        
        self.assertEqual(specialist.tenant_id, 1)
        self.assertIsNotNone(specialist.state_manager)
        self.assertIsNotNone(specialist.llm)
    
    def test_guest_id_extraction_pure(self):
        """Testa se extração de IDs é resiliente a tipos."""
        specialist = BaseSpecialist(tenant_id=1, specialist_name="TEST")
        
        self.assertEqual(specialist._get_guest_id_from_context({'guest_id': 123}), 123)
        self.assertEqual(specialist._get_guest_id_from_context({'guest_id': "123"}), 123)
        self.assertIsNone(specialist._get_guest_id_from_context({'guest_id': None}))
