import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from agents.specialists.validation import ValidationSpecialist
from agents.state_manager import StateManager

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def validation(mock_db):
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test_key'}):
        return ValidationSpecialist(mock_db, tenant_id=1, base_url="http://localhost:5173")

@pytest.mark.asyncio
async def test_validation_initialization(validation):
    """Testa inicialização."""
    assert validation.db is not None
    assert validation.tenant_id == 1
    assert validation.llm is not None
    assert len(validation.tools) == 5  # Agora com check_webhook_status

@pytest.mark.asyncio
async def test_validate_cpf_real(validation):
    """Testa validação de CPF com algoritmo real."""
    with patch('agents.shared_tools.validate_cpf_real') as mock_validate:
        mock_validate.return_value = {
            'valid': True,
            'cpf': '12345678909',
            'message': 'CPF válido'
        }
        
        tool = next((t for t in validation.tools if t.name == 'validate_cpf_real'), None)
        assert tool is not None
        result = await tool.ainvoke({"cpf": "123.456.789-09"})
        assert result['valid'] == True

@pytest.mark.asyncio
async def test_find_or_create_guest_found(validation):
    """Testa busca de hóspede encontrado."""
    with patch('agents.specialists.validation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {'validation_stage': 'cpf'}
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.validation.StateManager.update_state') as mock_update:
            with patch('agents.shared_tools.find_guest_logic') as mock_find:
                mock_find.return_value = {'id': 1, 'name': 'João Silva', 'cpf': '12345678909'}
                
                # Mock LLM
                mock_resp = MagicMock()
                mock_resp.content = "Hóspede encontrado."
                mock_resp.tool_calls = [{'name': 'find_or_create_guest', 'args': {'cpf': '12345678909'}, 'id': 'call_1'}]
                
                validation.llm_with_tools = AsyncMock()
                validation.llm_with_tools.ainvoke.return_value = mock_resp
                
                result = await validation.process("Meu CPF é 123.456.789-09", "session_123", {})
                assert result['specialist'] == 'validation'
                assert mock_update.called

@pytest.mark.asyncio
async def test_find_or_create_guest_not_found(validation):
    """Testa busca de hóspede não encontrado."""
    with patch('agents.specialists.validation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {'validation_stage': 'cpf'}
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.validation.StateManager.update_state') as mock_update:
            with patch('agents.shared_tools.find_guest_logic') as mock_find:
                mock_find.return_value = {
                    'error': 'Hóspede não encontrado.',
                    'registration_link': 'http://localhost:5173/1/registrar?cpf=12345678909'
                }
                
                # Mock LLM
                mock_resp = MagicMock()
                mock_resp.content = "Ainda não tenho seu cadastro."
                mock_resp.tool_calls = [{'name': 'find_or_create_guest', 'args': {'cpf': '12345678909'}, 'id': 'call_1'}]
                
                validation.llm_with_tools = AsyncMock()
                validation.llm_with_tools.ainvoke.return_value = mock_resp
                
                result = await validation.process("Meu CPF é 123.456.789-09", "session_123", {})
                assert 'registration_link' in result['response'] or 'registrar' in result['response'].lower()

@pytest.mark.asyncio
async def test_check_webhook_status_received(validation):
    """Testa detecção de webhook recebido."""
    with patch('agents.specialists.validation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        # Mocking the session state to return webhook_received=True
        mock_state.get_context.return_value = {
            'webhook_received': True,
            'guest_id': 1,
            'guest_name': 'João Silva'
        }
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.validation.StateManager.update_state') as mock_update:
            # Mock LLM calling check_webhook_status
            mock_resp = MagicMock()
            mock_resp.content = "Verificando seu cadastro..."
            mock_resp.tool_calls = [{'name': 'check_webhook_status', 'args': {'session_id': 'session_123'}, 'id': 'call_1'}]
            
            validation.llm_with_tools = AsyncMock()
            validation.llm_with_tools.ainvoke.return_value = mock_resp
            
            result = await validation.process("Já me cadastrei", "session_123", {})
            assert 'João Silva' in result['response']
            assert result['context']['validation_stage'] == 'companions'

@pytest.mark.asyncio
async def test_validate_companions_checklist_complete(validation):
    """Testa validação de checklist completo."""
    tool = next((t for t in validation.tools if t.name == 'validate_companions_checklist'), None)
    result = await tool.ainvoke({
        "group_size": 3,
        "companions": [{'name': 'João', 'age': 10}, {'name': 'Maria', 'age': 8}],
        "pricing_model": 'per_person'
    })
    assert result['status'] == 'complete'

@pytest.mark.asyncio
async def test_validate_companions_checklist_incomplete(validation):
    """Testa validação de checklist incompleto."""
    tool = next((t for t in validation.tools if t.name == 'validate_companions_checklist'), None)
    result = await tool.ainvoke({
        "group_size": 3,
        "companions": [{'name': 'João', 'age': 10}],
        "pricing_model": 'per_person'
    })
    assert result['status'] == 'incomplete'
