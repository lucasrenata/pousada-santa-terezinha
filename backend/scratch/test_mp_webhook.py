import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, set_tenant_context
import models
from routers.payments import handle_mercadopago_payment
from datetime import datetime
from unittest.mock import MagicMock, patch

def test_mp_webhook_alignment():
    tenant_id = 1
    # 1. Setup
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # Cleanup
        db.query(models.Booking).filter(models.Booking.notes.like("%Mercado Pago%")).delete()
        db.commit()

        booking = models.Booking(
            tenant_id=tenant_id,
            guest_id=3,
            room_id="101",
            check_in_date=datetime.now(),
            check_out_date=datetime.now(),
            total_guests=1,
            total_amount=500.0,
            deposit_amount=250.0,
            status="pendente",
            payment_status="pending"
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        b_id = booking.id
        print(f"✅ Reserva #{b_id} criada para teste MP.")

    # 2. Mockar o serviço do Mercado Pago para não fazer chamadas reais
    mock_response = {
        "response": {
            "status": "approved",
            "transaction_amount": 250.0,
            "payment_method_id": "pix",
            "metadata": {
                "tenant_id": tenant_id,
                "booking_id": b_id,
                "type": "reservation"
            }
        }
    }

    print("🚀 Simulando processamento de Webhook...")
    with patch("routers.payments.MercadoPagoService") as MockMP, \
         patch("routers.payments.get_tenant_mp_token") as MockToken:
        
        MockToken.return_value = "dummy_token"
        instance = MockMP.return_value
        instance.get_payment.return_value = mock_response
        
        db = SessionLocal()
        handle_mercadopago_payment(999999, db)
        
    # 3. Verificar resultados
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).get(b_id)
        
        print(f"📊 Status Final: {booking.status}")
        print(f"📊 Pagamento Final: {booking.payment_status}")
        print(f"📊 Nota: {booking.notes}")
        
        if booking.status == "confirmado" and booking.payment_status == "partial" and "Mercado Pago" in booking.notes:
            print("⭐ SUCESSO: Webhook alinhado com a automação!")
        else:
            print("❌ FALHA: Webhook não atualizou conforme esperado.")

if __name__ == "__main__":
    test_mp_webhook_alignment()
