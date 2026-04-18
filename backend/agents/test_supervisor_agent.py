import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Adiciona o diretório backend ao path para os imports funcionarem no teste
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.supervisor_agent import SupervisorAgent
from agents.state_manager import StateManager

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def supervisor(mock_db):
    return SupervisorAgent(mock_db, tenant_id=1)

@pytest.mark.asyncio
async def test_supervisor_initialization(supervisor):
    """Testa se SupervisorAgent inicializa sem erro."""
    assert supervisor.db is not None
    assert supervisor.tenant_id == 1
    assert supervisor.llm is not None

@pytest.mark.asyncio
async def test_decide_next_specialist(supervisor):
    """Testa decisão de specialist."""
    with patch.object(supervisor, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "discovery"
        
        specialist = await supervisor.decide_next_specialist(
            "DISCOVERY",
            "Quero ir no Hosana Brasil"
        )
        
        assert specialist in ["discovery", "validation", "confirmation", "payment", "none"]

@pytest.mark.asyncio
async def test_process_message(supervisor):
    """Testa processamento completo de mensagem."""
    # Usando patch no StateManager que é instanciado no __init__ do supervisor
    with patch.object(supervisor.state_manager, 'load_session') as mock_load:
        mock_state = Mock()
        mock_state.current_state = "DISCOVERY"
        mock_state.current_step = "DISCOVERY"
        mock_state.user_id = "test"
        mock_state.metadata = {}
        mock_state.get_context.return_value = {'current_step': 'DISCOVERY'}
        mock_load.return_value = mock_state
        
        with patch.object(supervisor, 'decide_next_specialist', new_callable=AsyncMock) as mock_decide:
            mock_decide.return_value = "discovery"
            
            # Patch update_state para evitar erro de banco real
            with patch.object(supervisor.state_manager, 'update_state') as mock_update:
                result = await supervisor.process("Quero uma reserva", "session_123")
                
                assert 'response' in result
                assert 'state' in result
                assert 'specialist' in result
                assert result['specialist'] in ["discovery", "validation", "confirmation", "payment", "none"]

if __name__ == '__main__':
    pytest.main([__file__])
