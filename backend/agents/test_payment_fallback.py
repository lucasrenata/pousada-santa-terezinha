"""
Teste direto do fallback de pagamento com chave PIX.
Cria uma reserva de teste real no banco e verifica se o agente apresenta a chave PIX.
"""
import sys
import asyncio
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal, set_tenant_context
import models
from agents.shared_tools import payment_info_logic, booking_creation_logic
from datetime import date

TENANT_ID = 1
TEST_CPF   = "12345678909"

def setup_test_booking():
    """Cria ou reutiliza um hóspede e uma reserva de teste."""
    with SessionLocal() as db:
        set_tenant_context(db, TENANT_ID)

        # Garante hóspede de teste
        guest = db.query(models.Guest).filter(models.Guest.document == TEST_CPF).first()
        if not guest:
            guest = models.Guest(
                name="João Simulação",
                document=TEST_CPF,
                email="joao@teste.com",
                tenant_id=TENANT_ID
            )
            db.add(guest)
            db.flush()

        # Garante um quarto de teste
        room = db.query(models.Room).filter(models.Room.tenant_id == TENANT_ID).first()
        if not room:
            print("❌ Nenhum quarto cadastrado. Cadastre ao menos um quarto no painel.")
            sys.exit(1)

        # Cria reserva de teste
        booking = models.Booking(
            tenant_id=TENANT_ID,
            guest_id=guest.id,
            room_id=room.id,
            check_in_date=date(2026, 5, 25),
            check_out_date=date(2026, 5, 26),
            total_guests=1,
            total_amount=300.0,
            status=models.BookingStatus.PENDENTE,
            payment_status=models.PaymentStatus.PENDENTE
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        print(f"✅ Reserva de teste criada: booking_id={booking.id} | Total: R$300,00")
        return booking.id

def test_payment_fallback(booking_id: int):
    """Testa o payment_info_logic e verifica o fallback PIX."""
    print(f"\n🔍 Testando payment_info_logic para booking #{booking_id}...\n")
    result = payment_info_logic(TENANT_ID, booking_id)

    print(f"📦 Resultado:")
    print(f"  booking_id     : {result.get('booking_id')}")
    print(f"  total          : R$ {result.get('total')}")
    print(f"  payment_method : {result.get('payment_method')}")
    print(f"  pix_qr         : {result.get('pix_qr')}")
    print(f"  manual_key     : {result.get('manual_key')}")

    method = result.get("payment_method")
    manual  = result.get("manual_key")

    if method == "mercadopago":
        print("\n✅ SUCESSO: Mercado Pago disponível e retornou QR Code!")
    elif method == "pix_manual" and manual:
        print(f"\n✅ SUCESSO: Fallback PIX funcionando! Chave → {manual}")
    else:
        print("\n❌ FALHA: Nenhuma forma de pagamento disponível. Verifique o banco.")
        sys.exit(1)

if __name__ == "__main__":
    booking_id = setup_test_booking()
    test_payment_fallback(booking_id)
    print("\n🏁 Teste de pagamento concluído com sucesso!")
