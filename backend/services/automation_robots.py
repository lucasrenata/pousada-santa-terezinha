import os
import sys
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Garantir que a pasta principal do backend está no path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, set_tenant_context
import models

def run_cleanup_robot(db: Session):
    """Cancela reservas pendentes sem comprovante após 30 minutos."""
    print("🤖 [ROBOT] Iniciando verificação de reservas pendentes expiradas...")
    try:
        # Define o contexto global para poder ver e processar todos os tenants
        set_tenant_context(db, -1)
        limit_time = datetime.now() - timedelta(minutes=30)
        
        expired_bookings = db.query(models.Booking).filter(
            models.Booking.status == models.BookingStatus.PENDENTE,
            models.Booking.payment_receipt_url == None,
            models.Booking.created_at <= limit_time
        ).all()
        
        for booking in expired_bookings:
            print(f"🤖 [ROBOT] Cancelando reserva expirada #{booking.id} do Tenant {booking.tenant_id}...")
            booking.status = models.BookingStatus.CANCELADO
            booking.payment_status = models.PaymentStatus.CANCELADO
            note_msg = "[SISTEMA] Reserva cancelada automaticamente por falta de pagamento do sinal após 30 minutos."
            if booking.notes:
                booking.notes += f"\n{note_msg}"
            else:
                booking.notes = note_msg
        
        if expired_bookings:
            db.commit()
            print(f"🤖 [ROBOT] Sucesso! {len(expired_bookings)} reservas expiradas foram canceladas.")
        else:
            print("🤖 [ROBOT] Nenhuma reserva pendente expirada encontrada.")
    except Exception as e:
        db.rollback()
        print(f"❌ [ROBOT ERROR] Erro durante a limpeza de reservas: {e}", file=sys.stderr)

def main_loop():
    print("🤖 [ROBOTS] Inicializando robôs de automação...")
    while True:
        try:
            db = SessionLocal()
            try:
                run_cleanup_robot(db)
            finally:
                db.close()
        except Exception as e:
            print(f"❌ [ROBOTS LOOP ERROR] Erro no loop de execução: {e}", file=sys.stderr)
        
        # Executar a cada 60 segundos
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
