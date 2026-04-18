import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Adiciona o diretório backend ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.specialists.discovery import DiscoverySpecialist
from agents.state_manager import StateManager

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def discovery(mock_db):
    return DiscoverySpecialist(mock_db, tenant_id=1)

@pytest.mark.asyncio
async def test_discovery_initialization(discovery):
    """Testa se DiscoverySpecialist inicializa sem erro."""
    assert discovery.db is not None
    assert discovery.tenant_id == 1
    assert discovery.llm is not None
    assert len(discovery.tools) == 2  # search_events e check_availability

@pytest.mark.asyncio
async def test_tools_defined(discovery):
    """Testa se as ferramentas estão definidas corretamente."""
    tool_names = [tool.name for tool in discovery.tools]
    assert 'search_events' in tool_names
    assert 'check_availability' in tool_names

@pytest.mark.asyncio
async def test_process_message_with_event(discovery):
    """Testa processamento de mensagem que menciona evento."""
    with patch.object(discovery.state_manager, 'load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {}
        mock_load.return_value = mock_state
        
        with patch.object(discovery.state_manager, 'update_state') as mock_update:
            # Mockar llm_with_tools como um todo para evitar erro de Pydantic/AttributeError
            discovery.llm_with_tools = AsyncMock()
            
            mock_response = Mock()
            mock_response.content = "Encontrei o evento Hosana Brasil!"
            mock_response.tool_calls = None
            discovery.llm_with_tools.ainvoke.return_value = mock_response
            
            result = await discovery.process(
                "Quero ir no Hosana Brasil",
                "session_123",
                {}
            )
            
            assert 'response' in result
            assert 'state' in result
            assert result['specialist'] == 'discovery'
            assert mock_update.called

@pytest.mark.asyncio
async def test_process_message_with_dates(discovery):
    """Testa processamento de mensagem que menciona datas."""
    with patch.object(discovery.state_manager, 'load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {}
        mock_load.return_value = mock_state
        
        with patch.object(discovery.state_manager, 'update_state') as mock_update:
            # Mockar llm_with_tools como um todo
            discovery.llm_with_tools = AsyncMock()
            
            mock_response = Mock()
            mock_response.content = "Temos quartos disponíveis de 15/12 a 20/12"
            mock_response.tool_calls = None
            discovery.llm_with_tools.ainvoke.return_value = mock_response
            
            result = await discovery.process(
                "Quero me hospedar de 15/12 a 20/12",
                "session_123",
                {}
            )
            
            assert 'response' in result
            assert 'state' in result

@pytest.mark.asyncio
async def test_error_handling(discovery):
    """Testa tratamento de erro."""
    with patch.object(discovery.state_manager, 'load_session') as mock_load:
        mock_load.side_effect = Exception("Database error")
        
        result = await discovery.process(
            "Quero uma reserva",
            "session_123",
            {}
        )
        
        assert 'problema' in result['response'].lower()
        assert result['state'] == 'DISCOVERY'
