import asyncio
import os
import sys

# Adiciona o diretório backend ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.customer_engine import CustomerEngineV2
from database import SessionLocal, set_tenant_context
import models
from datetime import datetime, timedelta

async def test_companions_booking():
    tenant_id = 1 # Ajuste se necessário
    engine = CustomerEngineV2(tenant_id)
    
    # 1. Setup: Criar um hóspede de teste se não existir
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        guest = db.query(models.Guest).filter(models.Guest.document == "12345678901").first()
        if not guest:
            guest = models.Guest(
                name="Hóspede Teste",
                document="12345678901",
                email="teste@exemplo.com",
                tenant_id=tenant_id
            )
            db.add(guest)
            db.commit()
            db.refresh(guest)
        guest_id = guest.id
        # Limpar reservas anteriores do teste para evitar conflito de disponibilidade
        old_bookings = db.query(models.Booking).filter(models.Booking.guest_id == guest.id).all()
        for ob in old_bookings:
            db.delete(ob)
        db.commit()

        # Garantir que o quarto 101 existe e está disponível
        room = db.query(models.Room).filter(models.Room.id == "101").first()
        if not room:
            room = models.Room(id="101", type="Suíte", price_per_night=200.0, max_capacity=4, tenant_id=tenant_id)
            db.add(room)
            db.commit()
        else:
            room.status = "disponivel"
            room.price_per_night = 200.0
            db.commit()

    # 2. Simular criação de reserva com acompanhantes (1 adulto, 1 criança de 8 anos)
    # Total de pessoas: 3 (Hóspede principal + 2 acompanhantes)
    companions = [
        {"name": "Adulto 2", "age": 30},
        {"name": "Criança", "age": 8}
    ]
    
    check_in = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    print(f"--- Iniciando reserva para Guest {guest_id} ---")
    result = await engine.robot_create_booking_atomic(
        guest_id=guest_id,
        room_ids="101",
        check_in=check_in,
        check_out=check_out,
        group_size=3,
        companions=companions
    )
    
    if result["success"]:
        print(f"✅ Reserva #{result['booking_id']} criada com sucesso!")
        print(f"💰 Valor Total: R$ {result['total_amount']:.2f}")
        print(f"💰 Sinal: R$ {result['down_payment']:.2f}")
        
        # 3. Validar no Banco
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(result["booking_id"])
            comps = db.query(models.Companion).filter(models.Companion.booking_id == booking.id).all()
            
            # Recalcula para ver o breakdown
            from utils.pricing import calculate_reservation_total
            settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
            days = (booking.check_out_date - booking.check_in_date).days
            guest_age = booking.guest.age if booking.guest and booking.guest.age else 18
            ages = [guest_age] + [c.age for c in comps]
            calc = calculate_reservation_total(booking.daily_rate, days, ages, settings=settings)
            
            print(f"📊 Breakdown: {calc['breakdown']}")
            print(f"📊 Acompanhantes no banco: {len(comps)}")
            for c in comps:
                print(f"   - {c.name}, {c.age} anos")
            
            # Verificação do preço esperado:
            # 2 adultos (full: 200 * 2 dias = 400 cada) = 800
            # 1 criança 8 anos (50%: 100 * 2 dias = 200) = 200
            # Total esperado: 1000
            if result['total_amount'] == 1000.0:
                 print("⭐ CÁLCULO DE PREÇO CORRETO!")
            else:
                 print(f"❌ CÁLCULO DE PREÇO INCORRETO (Esperado 1000, obtido {result['total_amount']})")
                 # Pode variar se as settings forem diferentes, mas por padrão é isso.
    else:
        print(f"❌ Erro ao criar reserva: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_companions_booking())
