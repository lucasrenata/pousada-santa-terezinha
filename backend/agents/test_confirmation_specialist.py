import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from agents.specialists.confirmation import ConfirmationSpecialist
from agents.state_manager import StateManager

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def confirmation(mock_db):
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test_key'}):
        return ConfirmationSpecialist(mock_db, tenant_id=1)

@pytest.mark.asyncio
async def test_confirmation_initialization(confirmation):
    """Testa inicialização."""
    assert confirmation.db is not None
    assert confirmation.tenant_id == 1
    assert confirmation.llm is not None
    assert len(confirmation.tools) == 3

@pytest.mark.asyncio
async def test_validate_booking_data_complete(confirmation):
    """Testa validação de dados completos."""
    tool = next((t for t in confirmation.tools if t.name == 'validate_booking_data'), None)
    context = {
        'guest_id': 1, 'guest_name': 'João Silva',
        'check_in': '2024-12-15', 'check_out': '2024-12-18',
        'room_id': '101', 'group_size': 3,
        'companions': [{'name': 'Maria', 'age': 32}],
        'total_price': 750.0
    }
    result = await tool.ainvoke({"context": context})
    assert result['valid'] == True

@pytest.mark.asyncio
async def test_validate_booking_data_incomplete(confirmation):
    """Testa validação de dados incompletos."""
    tool = next((t for t in confirmation.tools if t.name == 'validate_booking_data'), None)
    context = {'guest_id': 1, 'guest_name': 'João Silva'}
    result = await tool.ainvoke({"context": context})
    assert result['valid'] == False
    assert len(result['missing']) > 0

@pytest.mark.asyncio
async def test_format_summary(confirmation):
    """Testa formatação de resumo."""
    tool = next((t for t in confirmation.tools if t.name == 'format_summary'), None)
    context = {'guest_id': 1, 'total_price': 750.0}
    with patch('agents.shared_tools.format_booking_summary') as mock_format:
        mock_format.return_value = {'summary_text': 'Resumo formatado', 'total': 750.0}
        result = await tool.ainvoke({"context": context})
        assert 'summary_text' in result

@pytest.mark.asyncio
async def test_process_confirmation_positive(confirmation):
    """Testa processamento de confirmação positiva."""
    tool = next((t for t in confirmation.tools if t.name == 'process_confirmation_response'), None)
    result = await tool.ainvoke({"response": "Sim, está tudo certo!", "context": {}})
    assert result['confirmed'] == True
    assert result['next_state'] == 'PAYMENT'

@pytest.mark.asyncio
async def test_process_confirmation_negative(confirmation):
    """Testa processamento de confirmação negativa."""
    tool = next((t for t in confirmation.tools if t.name == 'process_confirmation_response'), None)
    result = await tool.ainvoke({"response": "Não, preciso corrigir", "context": {}})
    assert result['confirmed'] == False
    assert result['next_state'] == 'VALIDATION'

@pytest.mark.asyncio
async def test_process_confirmation_ambiguous(confirmation):
    """Testa processamento de resposta ambígua."""
    tool = next((t for t in confirmation.tools if t.name == 'process_confirmation_response'), None)
    result = await tool.ainvoke({"response": "Talvez", "context": {}})
    assert result['confirmed'] == None
    assert result['next_state'] == 'CONFIRMATION'

@pytest.mark.asyncio
async def test_process_message_show_summary(confirmation):
    """Testa processamento completo - exibir resumo."""
    with patch('agents.specialists.confirmation.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {
            'guest_id': 1, 'guest_name': 'João Silva',
            'check_in': '2024-12-15', 'check_out': '2024-12-18',
            'room_id': '101', 'group_size': 3,
            'companions': [{'name': 'Maria', 'age': 32}],
            'total_price': 750.0,
            'confirmation_stage': 'show_summary'
        }
        mock_load.return_value = mock_state
        
        with patch('agents.specialists.confirmation.StateManager.update_state') as mock_update:
            # Mock LLM
            mock_resp = MagicMock()
            mock_resp.content = "Aqui está seu resumo."
            mock_resp.tool_calls = [{'name': 'format_summary', 'args': {}, 'id': 'call_1'}]
            
            confirmation.llm_with_tools = AsyncMock()
            confirmation.llm_with_tools.ainvoke.return_value = mock_resp
            
            # Patch format_summary result
            with patch('agents.shared_tools.format_booking_summary') as mock_format:
                mock_format.return_value = {'summary_text': 'TEXTO FINAL', 'total': 750.0}
                
                result = await confirmation.process("Pode confirmar", "session_123", {})
                assert result['response'] == 'TEXTO FINAL'
                assert result['state'] == 'CONFIRMATION'
                assert mock_update.called
