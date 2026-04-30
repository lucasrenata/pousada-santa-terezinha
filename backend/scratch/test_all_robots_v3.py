import asyncio
import json
import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório atual ao path para encontrar os módulos
sys.path.append("/app")

from agents.customer_engine import CustomerEngineV2
from database import SessionLocal, set_tenant_context
import models

async def test_robots():
    tenant_id = 1
    engine = CustomerEngineV2(tenant_id)
    results = {}

    print(f"\n🚀 INICIANDO TESTE DOS ROBÔS (TENANT {tenant_id})")
    print("-" * 50)

    # 1. Teste Business Intelligence
    print("\n[1/6] Testando Inteligência de Negócio (Regras)...")
    res_bi = await engine.robot_business_intelligence()
    results["business_intelligence"] = res_bi
    print(f"✅ Sucesso: {res_bi.get('success')} | Regras encontradas: {len(res_bi.get('rules', []))}")

    # 2. Teste Identificação (CPF Fictício)
    print("\n[2/6] Testando Identificação de Hóspede...")
    res_id = await engine.robot_identify_guest("12345678901", "test_session_robos")
    results["identify_guest"] = res_id
    print(f"✅ Resultado: {res_id.get('message')}")

    # 3. Teste Cotação
    print("\n[3/6] Testando Cotação de Preços...")
    check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    res_quote = await engine.robot_calculate_quote(check_in, check_out, 2)
    results["calculate_quote"] = res_quote
    if res_quote.get("success"):
        print(f"✅ Opções encontradas: {len(res_quote.get('options', []))}")
    else:
        print(f"⚠️ Aviso: {res_quote.get('error')}")

    # 4. Teste Busca de Quartos
    print("\n[4/6] Testando Busca de Quartos Disponíveis...")
    res_rooms = await engine.robot_search_available_rooms(check_in, check_out, 2)
    results["search_rooms"] = res_rooms
    print(f"✅ Quartos encontrados: {len(res_rooms.get('rooms', [])) if res_rooms.get('success') else 0}")

    # 5. Teste Criação de Reserva (Se houver quarto e hóspede)
    # Vamos buscar um guest_id e room_id reais no banco para este teste
    print("\n[5/6] Testando Criação de Reserva Atômica...")
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        guest = db.query(models.Guest).first()
        room = db.query(models.Room).filter(models.Room.status == "disponivel").first()
        
        if guest and room:
            res_booking = await engine.robot_create_booking_atomic(guest.id, room.id, check_in, check_out, 2)
            results["create_booking"] = res_booking
            print(f"✅ Reserva criada ID: {res_booking.get('booking_id')}")
            
            # 6. Teste Pagamento
            print("\n[6/6] Testando Geração de Pagamento...")
            res_pay = await engine.robot_get_payment_info(res_booking.get("booking_id"))
            results["payment_info"] = res_pay
            print(f"✅ Link de pagamento: {res_pay.get('payment_method')}")
        else:
            print("⚠️ Pulo: Hóspede ou Quarto não encontrado no banco para criar reserva de teste.")

    print("\n" + "=" * 50)
    print("🏁 TESTE CONCLUÍDO")
    
if __name__ == "__main__":
    asyncio.run(test_robots())
