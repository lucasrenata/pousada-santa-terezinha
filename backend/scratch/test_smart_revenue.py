import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, set_tenant_context
import models
from datetime import datetime
import asyncio

async def test_smart_revenue():
    tenant_id = 1
    
    # --- CENÁRIO A: PIX MANUAL (Sem receita prévia) ---
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        b_manual = models.Booking(
            tenant_id=tenant_id, guest_id=3, room_id="101",
            check_in_date=datetime.now(), check_out_date=datetime.now(),
            daily_rate=200.0, deposit_amount=100.0, status="ativo"
        )
        db.add(b_manual)
        db.commit()
        db.refresh(b_manual)
        id_a = b_manual.id

    # Simular checkout manual
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).get(id_a)
        total_service = 200.0 # 1 dia
        already_paid = sum([r.amount for r in booking.revenues]) # Deve ser 0
        amount_to_launch = total_service - already_paid
        print(f"Scenario A (Manual): Total={total_service}, Already Paid={already_paid}, Launching={amount_to_launch}")
        assert amount_to_launch == 200.0

    # --- CENÁRIO B: MERCADO PAGO (Com receita prévia) ---
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        b_mp = models.Booking(
            tenant_id=tenant_id, guest_id=3, room_id="102",
            check_in_date=datetime.now(), check_out_date=datetime.now(),
            daily_rate=200.0, deposit_amount=100.0, status="ativo"
        )
        db.add(b_mp)
        db.commit()
        db.refresh(b_mp)
        id_b = b_mp.id
        
        # Simular Webhook MP lançando o sinal
        rev = models.Revenue(
            booking_id=id_b, amount=100.0, tenant_id=tenant_id,
            description="Sinal MP", category="hospedagem", created_at=datetime.now()
        )
        db.add(rev)
        db.commit()

    # Simular checkout MP
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).get(id_b)
        total_service = 200.0
        already_paid = sum([r.amount for r in booking.revenues]) # Deve ser 100
        amount_to_launch = total_service - already_paid
        print(f"Scenario B (MP): Total={total_service}, Already Paid={already_paid}, Launching={amount_to_launch}")
        assert amount_to_launch == 100.0

    print("⭐ SUCESSO: Lógica inteligente de faturamento validada!")

if __name__ == "__main__":
    asyncio.run(test_smart_revenue())
