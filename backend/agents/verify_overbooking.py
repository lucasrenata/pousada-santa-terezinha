import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal, set_tenant_context
from agents.shared_tools import booking_creation_logic, availability_check_logic
import models

async def verify_logic():
    tenant_id = 0
    room_id = "101"
    ci = "2026-10-25"
    co = "2026-10-26"
    
    print(f"\n🚀 Iniciando testes de Overbooking para Quarto {room_id}...")

    # 1. Limpa reservas de teste anteriores
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        db.query(models.Booking).filter(models.Booking.room_id == room_id, models.Booking.check_in_date == ci).delete()
        db.commit()

    # 2. Cria reserva PENDENTE inicial
    print("📌 Criando primeira reserva PENDENTE...")
    res1 = booking_creation_logic(tenant_id, 1, room_id, ci, co, 1)
    if res1.get("success"):
        print(f"✅ Reserva 1 criada. ID: {res1['booking_id']}")
    else:
        print(f"❌ Falha ao criar reserva 1: {res1.get('error')}")
        return

    # 3. Tenta criar segunda reserva para o mesmo período (Deve falhar)
    print("📌 Tentando criar segunda reserva para o MESMO período (deve falhar)...")
    res2 = booking_creation_logic(tenant_id, 1, room_id, ci, co, 1)
    if not res2.get("success"):
        print(f"✅ SUCESSO: O sistema bloqueou o overbooking! Erro: {res2.get('error')}")
    else:
        print(f"❌ FALHA: O sistema permitiu overbooking! ID: {res2.get('booking_id')}")

    # 4. Testa Expiração: Vamos 'envelhecer' a reserva 1 via SQL
    print("📌 Envelhecendo a reserva 1 para simular expiração (3 horas atrás)...")
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        b = db.query(models.Booking).get(res1["booking_id"])
        b.created_at = datetime.now() - timedelta(hours=3)
        db.commit()
    
    # 5. Verifica se a disponibilidade liberou o quarto
    print("📌 Verificando disponibilidade após expiração...")
    avail = availability_check_logic(tenant_id, ci, co, 1)
    available_rooms = [r["room_number"] for r in avail.get("rooms", [])]
    if room_id in available_rooms:
        print(f"✅ SUCESSO: O quarto {room_id} foi liberado pós-expiração!")
    else:
        print(f"❌ FALHA: O quarto {room_id} continua ocupado mesmo após 3 horas.")

if __name__ == "__main__":
    asyncio.run(verify_logic())
