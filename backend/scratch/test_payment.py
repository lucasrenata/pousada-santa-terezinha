import asyncio
import sys
import os
import json

sys.path.append("/app")
from database import SessionLocal
from agents.customer_engine import CustomerEngineV2

async def test_payment_tools():
    tenant_id = 1
    db = SessionLocal()
    engine = CustomerEngineV2(tenant_id)
    
    print("\n--- TESTANDO ROBÔS DE PAGAMENTO ---")
    
    # 1. Simular uma reserva rápida no DB para ter um booking_id real
    try:
        # Pega qualquer hospede e quarto disponivel
        from models import Guest, Room
        guest = db.query(Guest).first()
        room = db.query(Room).first()
        
        if not guest or not room:
            print("❌ Crie um hóspede e um quarto primeiro.")
            return

        print(f"✅ Usando Hóspede: {guest.id} | Quarto: {room.id}")
        
        # Chama a criação atômica
        reserva = await engine.robot_create_booking_atomic(
            guest_id=guest.id, 
            room_id=room.id, 
            check_in="2026-05-01", 
            check_out="2026-05-02", 
            group_size=2
        )
        print("\n📦 RETORNO DO ROBÔ DE CRIAÇÃO DA RESERVA:")
        print(json.dumps(reserva, indent=2, ensure_ascii=False))
        
        if reserva.get("success"):
            # Chama a info de pagamento
            pagamento = await engine.robot_get_payment_info(reserva["booking_id"])
            print("\n💳 RETORNO DO ROBÔ DE PAGAMENTO:")
            print(json.dumps(pagamento, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_payment_tools())
