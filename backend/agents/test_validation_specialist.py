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
    assert validation.db is not None
    assert validation.tenant_id == 1
    assert validation.llm is not None
    assert len(validation.tools) == 4

@pytest.mark.asyncio
async def test_validate_cpf_format(validation):
    tool = next((t for t in validation.tools if t.name == 'validate_cpf_format'), None)
    result = await tool.ainvoke({"cpf": "123.456.789-09"})
    assert result['valid'] == True
    result = await tool.ainvoke({"cpf": "123"})
    assert result['valid'] == False

@pytest.mark.asyncio
async def test_find_or_create_guest_not_found(validation):
    with patch('agents.specialists.validation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {'validation_stage': 'cpf'}
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.validation.StateManager.update_state') as mock_update:
            with patch('agents.shared_tools.find_guest_logic') as mock_find:
                mock_find.return_value = {
                    'error': 'Hóspede não encontrado.',
                    'registration_link': 'http://localhost:5173/1/registrar?cpf=12345678900'
                }
                
                # Garantir que o banco retorne None para hóspede não encontrado
                validation.db.query().filter().first.return_value = None
                
                mock_resp = MagicMock()
                mock_resp.content = "Ainda não tenho seu cadastro."
                mock_resp.tool_calls = [{
                    'name': 'find_or_create_guest',
                    'args': {'cpf': '12345678900'},
                    'id': 'call_1'
                }]
                
                validation.llm_with_tools = AsyncMock()
                validation.llm_with_tools.ainvoke.return_value = mock_resp
                
                result = await validation.process(
                    "Meu CPF é 123.456.789-09",
                    "session_123",
                    {}
                )
                
                assert 'registration_link' in result['response'] or 'registrar' in result['response'].lower()
                assert mock_update.called

@pytest.mark.asyncio
async def test_validate_companions_checklist(validation):
    tool = next((t for t in validation.tools if t.name == 'validate_companions_checklist'), None)
    result = await tool.ainvoke({"group_size": 3, "companions": [{'name': 'João', 'age': 10}], "pricing_model": 'per_person'})
    assert result['status'] == 'incomplete'
    result = await tool.ainvoke({"group_size": 3, "companions": [{'name': 'João', 'age': 10}, {'name': 'Maria', 'age': 8}], "pricing_model": 'per_person'})
    assert result['status'] == 'complete'

@pytest.mark.asyncio
async def test_validate_age(validation):
    tool = next((t for t in validation.tools if t.name == 'validate_age'), None)
    result = await tool.ainvoke({"age": 25})
    assert result['valid'] == True
    result = await tool.ainvoke({"age": 200})
    assert result['valid'] == False

@pytest.mark.asyncio
async def test_process_message(validation):
    with patch('agents.specialists.validation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {'validation_stage': 'cpf'}
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.validation.StateManager.update_state') as mock_update:
            mock_response = MagicMock()
            mock_response.content = "Perfeito! Encontrei você no sistema."
            mock_response.tool_calls = None
            
            validation.llm_with_tools = AsyncMock()
            validation.llm_with_tools.ainvoke.return_value = mock_response
                
            result = await validation.process("Meu CPF é 123.456.789-09", "session_123", {})
            assert 'response' in result
            assert 'state' in result
            assert result['specialist'] == 'validation'
            assert mock_update.called

@pytest.mark.asyncio
async def test_companions_loop_check(validation):
    tool = next((t for t in validation.tools if t.name == 'validate_companions_checklist'), None)
    result = await tool.ainvoke({"group_size": 2, "companions": [{'name': 'Criança'}], "pricing_model": 'per_person'})
    assert result['ready'] == False
    assert any("idade não informada" in m for m in result['missing'])
