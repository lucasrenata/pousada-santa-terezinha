import sys
import asyncio
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from agents.shared_tools import execute_business_logic
from database import SessionLocal, set_tenant_context
import models

async def test_agent_scenarios():
    tenant_id = 0
    session_id = "agent_tool_final_test"
    
    # 1. TESTE: Busca de Disponibilidade
    print("\n🔍 --- SCENARIO 1: Busca de Disponibilidade ---")
    context = {"current_state": "DISCOVERY", "check_in": "2026-10-25", "check_out": "2026-10-26", "group_size": 1}
    results = await execute_business_logic(tenant_id, "quero quartos", context, session_id)
    if "availability" in results:
        print(f"✅ SUCESSO: Disponibilidade acionada.")
    else:
        print("❌ FALHA: Disponibilidade não acionada.")

    # 2. TESTE: Identificação de Hóspede
    print("\n🔍 --- SCENARIO 2: Identificação de Hóspede ---")
    context = {"current_state": "DISCOVERY", "cpf": "39096893883"}
    results = await execute_business_logic(tenant_id, "meu cpf é esse", context, session_id)
    if "guest" in results:
        print(f"✅ SUCESSO: Hóspede identificado: {results['guest'].get('name')}")
    else:
        print("❌ FALHA: Hóspede não identificado.")

    # 3. TESTE: Cálculo de Sinal (50%)
    print("\n🔍 --- SCENARIO 3: Cálculo de Sinal (50%) ---")
    # Garante 50% no DB
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        db.query(models.SystemSetting).filter(models.SystemSetting.key == 'pousada_deposit_percentage').update({"value": "50"})
        db.commit()
    
    context = {"current_state": "PAYMENT", "booking_id": 5, "total_price": 150.0, "guest_id": 1}
    results = await execute_business_logic(tenant_id, "como pago?", context, session_id)
    payment = results.get("payment")
    if payment and payment.get("amount") == 75.0:
        print(f"✅ SUCESSO: Sinal calculado corretamente (R$ 75.0).")
    else:
        print(f"❌ FALHA: Sinal incorreto: {payment.get('amount') if payment else 'Nada'}")

    # 4. TESTE: Overbooking
    print("\n🔍 --- SCENARIO 4: Proteção de Overbooking ---")
    context = {"current_state": "CONFIRMATION", "guest_id": 1, "room_id": "101", "check_in": "2026-12-25", "check_out": "2026-12-26", "group_size": 1}
    # Segunda tentativa para o mesmo quarto/data
    results = await execute_business_logic(tenant_id, "sim", context, "session_overlap")
    if results.get("booking_error"):
         print(f"✅ SUCESSO: Overbooking bloqueado: {results['booking_error']}")
    else:
         print("❌ FALHA: Overbooking não foi bloqueado.")

if __name__ == "__main__":
    asyncio.run(test_agent_scenarios())
