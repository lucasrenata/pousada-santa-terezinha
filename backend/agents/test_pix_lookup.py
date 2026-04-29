import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal, set_tenant_context
from agents.shared_tools import payment_info_logic
import models

def test_lookup(tenant_id: int):
    print(f"\n--- Testando lookup de PIX para Tenant {tenant_id} ---")
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # Simula a existência de uma reserva para o teste
        booking = db.query(models.Booking).filter(models.Booking.tenant_id == tenant_id).first()
        if not booking:
            print(f"❌ Nenhuma reserva encontrada para o tenant {tenant_id}. Criando uma...")
            booking = models.Booking(
                tenant_id=tenant_id,
                guest_id=1,
                room_id="101",
                check_in_date="2026-05-25",
                check_out_date="2026-05-26",
                total_guests=1,
                total_amount=300.0,
                status=models.BookingStatus.PENDENTE
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
        
        print(f"🔍 Chamando payment_info_logic para booking {booking.id}...")
        result = payment_info_logic(tenant_id, booking.id)
        print(f"📦 Resultado Final: {result}")

if __name__ == "__main__":
    test_lookup(0)
    test_lookup(1)
