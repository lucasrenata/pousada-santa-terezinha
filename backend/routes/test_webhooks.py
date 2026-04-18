import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app
import models

client = TestClient(app)

class TestMercadoPagoWebhook:
    
    def test_webhook_payment_approved(self):
        """Testa webhook de pagamento aprovado."""
        request_id = "test-request-123"
        payload = {
            "action": "payment.updated",
            "data": {
                "id": 1234567890,
                "status": "approved",
                "external_reference": "123",
                "amount": 750.00,
                "payer_email": "hospede@example.com"
            }
        }
        
        body = json.dumps(payload).encode('utf-8')
        secret = "test_secret"
        
        # Calcular assinatura
        data_to_sign = request_id + body.decode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            data_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        with patch.dict('os.environ', {'MERCADOPAGO_WEBHOOK_SECRET': secret}):
            with patch('routes.webhooks.SessionLocal') as mock_session:
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                
                mock_booking = MagicMock()
                mock_booking.id = 123
                mock_booking.tenant_id = 1
                mock_booking.total_amount = 750.00
                mock_booking.guest = Mock(email='hospede@example.com')
                mock_db.query.return_value.get.return_value = mock_booking
                
                response = client.post(
                    "/api/webhooks/mercadopago",
                    content=body,
                    headers={
                        'X-Signature': f'sha256={signature}',
                        'X-Request-ID': request_id,
                        'Content-Type': 'application/json'
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data['success'] == True

    def test_webhook_invalid_signature(self):
        """Testa webhook com assinatura inválida."""
        payload = {"action": "payment.updated", "data": {"id": 1, "status": "approved", "external_reference": "123"}}
        response = client.post(
            "/api/webhooks/mercadopago",
            json=payload,
            headers={'X-Signature': 'sha256=invalid', 'X-Request-ID': 'req1'}
        )
        assert response.status_code == 401

    def test_webhook_missing_signature(self):
        """Testa webhook sem assinatura."""
        payload = {"action": "payment.updated", "data": {"id": 1, "status": "approved", "external_reference": "123"}}
        response = client.post("/api/webhooks/mercadopago", json=payload)
        assert response.status_code == 400

    def test_webhook_payment_rejected(self):
        """Testa webhook de pagamento rejeitado."""
        request_id = "test-req-rej"
        payload = {"action": "payment.updated", "data": {"id": 1, "status": "rejected", "external_reference": "123"}}
        body = json.dumps(payload).encode('utf-8')
        secret = "test_secret"
        data_to_sign = request_id + body.decode('utf-8')
        signature = hmac.new(secret.encode('utf-8'), data_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        with patch.dict('os.environ', {'MERCADOPAGO_WEBHOOK_SECRET': secret}):
            with patch('routes.webhooks.SessionLocal') as mock_session:
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                mock_booking = MagicMock(id=123, tenant_id=1)
                mock_db.query.return_value.get.return_value = mock_booking

                response = client.post(
                    "/api/webhooks/mercadopago",
                    content=body,
                    headers={
                        'X-Signature': f'sha256={signature}',
                        'X-Request-ID': request_id,
                        'Content-Type': 'application/json'
                    }
                )
                assert response.status_code == 200
                assert response.json()['success'] == True

class TestGuestRegistrationWebhook:
    
    def test_webhook_guest_registered(self):
        """Testa webhook de cadastro de hóspede."""
        payload = {
            "tenant_id": 1,
            "cpf": "123.456.789-09",
            "session_id": "session_123",
            "guest_data": {"name": "João Silva"}
        }
        
        with patch('agents.shared_tools.handle_guest_registration_webhook') as mock_handle:
            mock_handle.return_value = {'success': True}
            response = client.post("/api/webhooks/guest-registered", json=payload)
            assert response.status_code == 200
            assert response.json()['success'] == True
