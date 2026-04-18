import pytest
from unittest.mock import Mock, patch
from agents import shared_tools
from datetime import datetime, date

class TestValidateCpfReal:
    """Testa validação de CPF com algoritmo real."""
    
    def test_valid_cpf(self):
        """Testa CPF válido."""
        with patch('agents.shared_tools._cpf_valid', return_value=True):
            result = shared_tools.validate_cpf_real("123.456.789-09")
            assert result['valid'] == True
            assert result['cpf'] == "12345678909"
    
    def test_invalid_cpf_format(self):
        """Testa CPF com formato inválido."""
        result = shared_tools.validate_cpf_real("123")
        assert result['valid'] == False
        assert 'dígitos' in result['message'].lower()
    
    def test_invalid_cpf_algorithm(self):
        """Testa CPF que falha no algoritmo."""
        with patch('agents.shared_tools._cpf_valid', return_value=False):
            result = shared_tools.validate_cpf_real("12345678900")
            assert result['valid'] == False
            assert 'inválido' in result['message'].lower()


class TestPreviewBookingPrice:
    """Testa cálculo de preço em preview."""
    
    def test_preview_price_success(self):
        """Testa cálculo de preço com sucesso."""
        with patch('agents.shared_tools.SessionLocal') as mock_session:
            with patch('agents.shared_tools.calculate_booking_quote') as mock_calc:
                # Mock config mock
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.query().all.return_value = [] # settings
                
                mock_calc.return_value = {
                    'total': 500.0,
                    'days': 3,
                    'notes': 'Tarifa Padrão',
                    'event_name': None
                }
                
                result = shared_tools.preview_booking_price(
                    tenant_id=1,
                    room_id='101',
                    check_in='15/12',
                    check_out='18/12',
                    group_size=2,
                    ages=[35, 32]
                )
                
                assert result['total'] == 500.0
                assert result['days'] == 3
                assert 'pricing_model' in result


class TestFormatBookingSummary:
    """Testa formatação de resumo de reserva."""
    
    def test_format_summary_success(self):
        """Testa formatação de resumo com sucesso."""
        context = {
            'guest_id': 1,
            'guest_name': 'João Silva',
            'check_in': date(2024, 12, 15),
            'check_out': date(2024, 12, 18),
            'room_id': '101',
            'group_size': 3,
            'companions': [
                {'name': 'Maria Silva', 'age': 32},
                {'name': 'Pedro Silva', 'age': 8}
            ],
            'total_price': 750.0
        }
        
        with patch('agents.shared_tools.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            mock_room = Mock()
            mock_room.type = 'Quarto Duplo'
            mock_room.id = '101'
            mock_db.query.return_value.get.return_value = mock_room
            
            result = shared_tools.format_booking_summary(1, context)
            
            assert 'summary_text' in result
            assert 'João Silva' in result['summary_text']
            assert 'R$ 750.00' in result['summary_text']
            assert result['total'] == 750.0


class TestReissuePaymentQr:
    """Testa reemissão de QR Code."""
    
    def test_reissue_qr_success(self):
        """Testa reemissão de QR Code com sucesso."""
        with patch('agents.shared_tools.payment_info_logic') as mock_payment:
            mock_payment.return_value = {
                'booking_id': 123,
                'total': 500.0,
                'pix_qr': {
                    'image': 'base64...',
                    'code': '00020126...',
                    'link': 'https://...'
                }
            }
            
            result = shared_tools.reissue_payment_qr(1, 123)
            
            assert result['booking_id'] == 123
            assert 'pix_qr' in result


class TestHandleGuestRegistrationWebhook:
    """Testa webhook de registro de hóspede."""
    
    def test_webhook_success(self):
        """Testa webhook com sucesso."""
        with patch('agents.shared_tools.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            mock_guest = Mock()
            mock_guest.id = 1
            mock_guest.name = 'João Silva'
            # Corrigido para um único .filter()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_guest
            
            # Mock state manager update
            with patch('agents.shared_tools.StateManager') as mock_sm_class:
                mock_sm = Mock()
                mock_sm_class.return_value = mock_sm
                
                mock_session_state = Mock()
                mock_session_state.get_context.return_value = {} # Retorna um dict real
                mock_sm.load_session.return_value = mock_session_state
                
                result = shared_tools.handle_guest_registration_webhook(
                    tenant_id=1,
                    cpf='123.456.789-09',
                    session_id='session_123'
                )
                
                # Se falhar, vamos ver o erro
                if not result['success']:
                    print(f"Erro no webhook: {result.get('error')}")
                
                assert result['success'] == True
                assert result['guest_id'] == 1
                assert result['webhook_received'] == True
    
    def test_webhook_guest_not_found(self):
        """Testa webhook quando hóspede não existe."""
        with patch('agents.shared_tools.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            result = shared_tools.handle_guest_registration_webhook(
                tenant_id=1,
                cpf='999.999.999-99'
            )
            
            assert result['success'] == False
            assert 'não encontrado' in result['error'].lower()
