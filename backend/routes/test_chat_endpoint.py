import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Adiciona o diretório backend ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from agents.state_manager import StateManager

client = TestClient(app)

@pytest.fixture
def mock_db():
    return Mock()

class TestChatEndpoint:
    
    def test_health_check(self):
        """Testa health check."""
        response = client.get("/api/v1/chat/health")
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
    
    def test_chat_message_success(self):
        """Testa envio de mensagem com sucesso."""
        with patch('routes.chat.validate_tenant') as mock_tenant:
            mock_tenant.return_value = Mock(id=1, name="Pousada Test")
            
            with patch('routes.chat.validate_session') as mock_session:
                mock_state = Mock()
                mock_state.current_state = 'DISCOVERY'
                mock_state.get_context.return_value = {}
                mock_session.return_value = mock_state
                
                with patch('routes.chat.SupervisorAgent') as mock_supervisor:
                    mock_sup_instance = AsyncMock()
                    mock_sup_instance.process = AsyncMock(return_value={
                        'response': 'Olá! Como posso ajudar?',
                        'state': 'DISCOVERY',
                        'specialist': 'discovery',
                        'context': {}
                    })
                    mock_supervisor.return_value = mock_sup_instance
                    
                    response = client.post(
                        "/api/v1/chat/message",
                        json={
                            "message": "Quero uma reserva",
                            "session_id": "test_session",
                            "tenant_id": 1
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert 'response' in data
                    assert 'state' in data
                    assert 'specialist' in data
    
    def test_chat_message_invalid_tenant(self):
        """Testa erro quando tenant não existe."""
        with patch('routes.chat.validate_tenant') as mock_tenant:
            mock_tenant.side_effect = Exception("Tenant not found")
            
            response = client.post(
                "/api/v1/chat/message",
                json={
                    "message": "Quero uma reserva",
                    "session_id": "test_session",
                    "tenant_id": 999
                }
            )
            
            assert response.status_code == 500
    
    def test_chat_message_empty_message(self):
        """Testa erro quando mensagem está vazia."""
        response = client.post(
            "/api/v1/chat/message",
            json={
                "message": "",
                "session_id": "test_session",
                "tenant_id": 1
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_rate_limit(self):
        """Testa rate limiting."""
        # Reset rate limiter memory for this test if possible, 
        # but here we just use a unique session_id
        session_id = "rate_limit_unique_test"
        
        with patch('routes.chat.validate_tenant') as mock_tenant:
            mock_tenant.return_value = Mock(id=1, name="Pousada Test")
            
            with patch('routes.chat.validate_session') as mock_session:
                mock_state = Mock()
                mock_state.current_state = 'DISCOVERY'
                mock_state.get_context.return_value = {}
                mock_session.return_value = mock_state
                
                with patch('routes.chat.SupervisorAgent') as mock_supervisor:
                    mock_sup_instance = AsyncMock()
                    mock_sup_instance.process = AsyncMock(return_value={
                        'response': 'OK',
                        'state': 'DISCOVERY',
                        'specialist': 'discovery',
                        'context': {}
                    })
                    mock_supervisor.return_value = mock_sup_instance
                    
                    # Enviar 11 requisições (limite é 10)
                    for i in range(11):
                        response = client.post(
                            "/api/v1/chat/message",
                            json={
                                "message": f"Mensagem {i}",
                                "session_id": session_id,
                                "tenant_id": 1
                            }
                        )
                        
                        if i < 10:
                            assert response.status_code == 200
                        else:
                            assert response.status_code == 429
    
    def test_get_session_state(self):
        """Testa obtenção do estado da sessão."""
        with patch('routes.chat.validate_tenant') as mock_tenant:
            mock_tenant.return_value = Mock(id=1, name="Pousada Test")
            
            with patch('routes.chat.StateManager') as mock_state_mgr:
                mock_instance = Mock()
                mock_state = Mock()
                mock_state.current_state = 'DISCOVERY'
                mock_state.get_context.return_value = {'guest_id': 1}
                mock_state.created_at = Mock(isoformat=Mock(return_value='2024-01-01T00:00:00'))
                mock_instance.load_session.return_value = mock_state
                mock_instance.get_state_and_history.return_value = ('DISCOVERY', [])
                mock_state_mgr.return_value = mock_instance
                
                response = client.get(
                    f"/api/v1/chat/session/test_session?tenant_id=1"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data['session_id'] == 'test_session'
                assert data['current_state'] == 'DISCOVERY'
