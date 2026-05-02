import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, set_tenant_context
import models
from datetime import datetime
import asyncio

async def test_internal_receipt_logic():
    tenant_id = 1
    # 1. Criar uma reserva pendente limpa
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # Cleanup
        db.query(models.Booking).filter(models.Booking.notes.like("%[SISTEMA]%")).delete()
        db.commit()

        booking = models.Booking(
            tenant_id=tenant_id,
            guest_id=3, # Hóspede do teste anterior
            room_id="101",
            check_in_date=datetime.now(),
            check_out_date=datetime.now(),
            total_guests=1,
            total_amount=200.0,
            deposit_amount=100.0,
            status="pendente",
            payment_status="pending"
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        b_id = booking.id
        print(f"✅ Reserva de teste #{b_id} criada com status: {booking.status}")

    # 2. Chamar o endpoint via requests (interno ao container)
    import requests
    # Uvicorn costuma rodar na porta 8008 internamente no Dockerfile? 
    # De acordo com docker ps, é 8008->8008.
    
    # Criar dummy file
    with open("dummy.jpg", "wb") as f:
        f.write(b"test")
    
    url = f"http://localhost:8000/bookings/{b_id}/receipt?tenant_id={tenant_id}"
    files = {'file': ('dummy.jpg', open('dummy.jpg', 'rb'), 'image/jpeg')}
    
    print(f"🚀 Enviando comprovante para {url}...")
    resp = requests.post(url, files=files)
    
    if resp.status_code == 200:
        print("✅ Resposta 200 OK do servidor.")
        
        # 3. Verificar se o banco atualizou
        with SessionLocal() as db:
            set_tenant_context(db, tenant_id)
            booking = db.query(models.Booking).get(b_id)
            print(f"📊 Novo Status: {booking.status}")
            print(f"📊 Novo Pagamento: {booking.payment_status}")
            print(f"📊 Nota: {booking.notes}")
            
            if booking.status == "confirmado" and booking.payment_status == "partial" and "[SISTEMA]" in (booking.notes or ""):
                print("⭐ SUCESSO: Automação funcionando perfeitamente!")
            else:
                print("❌ FALHA: Status ou notas não atualizados corretamente.")
    else:
        print(f"❌ Erro no request: {resp.status_code} - {resp.text}")

    if os.path.exists("dummy.jpg"):
        os.remove("dummy.jpg")

if __name__ == "__main__":
    asyncio.run(test_internal_receipt_logic())
