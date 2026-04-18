import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from agents.specialists.payment import PaymentSpecialist
import models

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def payment(mock_db):
    with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test_key'}):
        return PaymentSpecialist(mock_db, tenant_id=1)

@pytest.mark.asyncio
async def test_payment_initialization(payment):
    """Testa inicialização."""
    assert payment.db is not None
    assert payment.tenant_id == 1
    assert len(payment.tools) == 5

@pytest.mark.asyncio
async def test_generate_payment_qr(payment):
    """Testa geração de QR Code."""
    with patch('agents.shared_tools.payment_info_logic') as mock_logic:
        mock_logic.return_value = {'pix_qr': {'code': '000201...'}, 'total': 100.0}
        tool = next((t for t in payment.tools if t.name == 'generate_payment_qr'), None)
        result = await tool.ainvoke({"booking_id": 123})
        assert 'pix_qr' in result

@pytest.mark.asyncio
async def test_format_payment_instructions(payment):
    """Testa formatação visual."""
    tool = next((t for t in payment.tools if t.name == 'format_payment_instructions'), None)
    data = {'booking_id': 123, 'total': 150.0, 'pix_qr': {'code': 'XYZ'}, 'manual_key': 'abc@pix'}
    result = await tool.ainvoke({"payment_data": data})
    assert 'instructions_text' in result
    assert '150.00' in result['instructions_text']

@pytest.mark.asyncio
async def test_check_payment_status_confirmed(payment, mock_db):
    """Testa detecção de pagamento no banco (Sucesso)."""
    mock_booking = Mock()
    mock_booking.status = models.BookingStatus.CONFIRMADO
    mock_db.query.return_value.get.return_value = mock_booking
    
    tool = next((t for t in payment.tools if t.name == 'check_payment_status'), None)
    result = await tool.ainvoke({"booking_id": 123})
    assert result['confirmed'] == True
    assert result['status'] == 'CONFIRMADO'

@pytest.mark.asyncio
async def test_check_payment_status_pending(payment, mock_db):
    """Testa detecção de pagamento no banco (Pendente)."""
    mock_booking = Mock()
    mock_booking.status = models.BookingStatus.PENDENTE
    mock_db.query.return_value.get.return_value = mock_booking
    
    tool = next((t for t in payment.tools if t.name == 'check_payment_status'), None)
    result = await tool.ainvoke({"booking_id": 123})
    assert result['confirmed'] == False

@pytest.mark.asyncio
async def test_process_payment_confirmation_positive(payment):
    """Testa parser de resposta positiva."""
    with patch('agents.shared_tools.confirm_payment_logic') as mock_confirm:
        mock_confirm.return_value = {'success': True}
        tool = next((t for t in payment.tools if t.name == 'process_payment_confirmation'), None)
        result = await tool.ainvoke({"response": "Já paguei!", "booking_id": 123})
        assert result['payment_confirmed'] == True

@pytest.mark.asyncio
async def test_reissue_payment_qr(payment):
    """Testa reemissão."""
    with patch('agents.shared_tools.reissue_payment_qr') as mock_reissue:
        mock_reissue.return_value = {'pix_qr': {'code': 'NEW_CODE'}}
        tool = next((t for t in payment.tools if t.name == 'reissue_payment_qr_tool'), None)
        result = await tool.ainvoke({"booking_id": 123})
        assert result['pix_qr']['code'] == 'NEW_CODE'

@pytest.mark.asyncio
async def test_process_message_awaiting_payment(payment, mock_db):
    """Testa fluxo completo de espera e monitoramento."""
    with patch('agents.specialists.payment.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {
            'booking_id': 123, 'payment_stage': 'awaiting_confirmation'
        }
        mock_load.return_value = mock_state
        
        # Mocking LLM calling check_payment_status
        mock_resp = MagicMock()
        mock_resp.content = "Ainda estou aguardando."
        mock_resp.tool_calls = [{'name': 'check_payment_status', 'args': {'booking_id': 123}, 'id': 'call_1'}]
        
        payment.llm_with_tools = AsyncMock()
        payment.llm_with_tools.ainvoke.return_value = mock_resp
        
        # Mocking DB response for confirmed
        mock_booking = Mock()
        mock_booking.status = models.BookingStatus.CONFIRMADO
        mock_db.query.return_value.get.return_value = mock_booking
        
        with patch('agents.specialists.payment.StateManager.update_state') as mock_update:
            result = await payment.process("Já caiu o PIX?", "session_123", {})
            assert 'confirmada' in result['response'].lower()
            assert result['state'] == 'COMPLETE'
            assert mock_update.called

@pytest.mark.asyncio
async def test_process_message_fail_booking_creation(payment):
    """Testa falha na criação da reserva se não existir booking_id."""
    with patch('agents.specialists.payment.StateManager.load_session') as mock_load:
        mock_state = Mock()
        mock_state.get_context.return_value = {'payment_stage': 'generate_qr'} # No booking_id
        mock_load.return_value = mock_state
        
        with patch('agents.shared_tools.unified_booking_flow') as mock_flow:
            mock_flow.return_value = {'error': 'Quarto indisponível'}
            result = await payment.process("Pagar", "session_123", {})
            assert 'Erro' in result['response']
            assert result['state'] == 'PAYMENT'
