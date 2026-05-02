import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, set_tenant_context
import models
import shutil
from fastapi import UploadFile
import io

async def verify_receipt_db():
    tenant_id = 1
    booking_id = 14 # ID do teste anterior
    
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        booking = db.query(models.Booking).get(booking_id)
        if not booking:
            print(f"❌ Reserva {booking_id} não encontrada.")
            return

        print(f"--- Estado ANTES do upload ---")
        print(f"Status: {booking.status}")
        print(f"Pagamento: {booking.payment_status}")
        print(f"Nota: {booking.notes}")
        
        # Simular o upload chamando a lógica do router (ou apenas chamando o endpoint via requests se o container tiver requests)
        # Mais fácil: vamos apenas rodar o script que usa requests dentro do container.
        
import asyncio
if __name__ == "__main__":
    # Na verdade, vou simplificar: vou rodar um script que faz o upload e depois checa o banco.
    pass
