import sys
import os
sys.path.append('c:\\projetos\\PousadaSystem\\backend')

from database import SessionLocal, set_tenant_context
import os
os.environ["DATABASE_URL"] = "postgresql://admin:admin_password_123@localhost:5434/pousada_db"
import models
from datetime import datetime, timedelta
from utils.pricing import calculate_daily_rates_count

db = SessionLocal()
tenant_id = 1
set_tenant_context(db, tenant_id)

check_in = "2026-10-10"
check_out = "2026-10-15"
group_size = 2

ci = datetime.strptime(check_in, "%Y-%m-%d").date()
co = datetime.strptime(check_out, "%Y-%m-%d").date()

event = db.query(models.Event).filter(models.Event.start_date <= co, models.Event.end_date >= ci).first()
days = calculate_daily_rates_count(ci, co, "14:00", "14:00")
settings = {s.key: s.value for s in db.query(models.SystemSetting).all()}
active_rules = db.query(models.BusinessRule).filter(models.BusinessRule.is_active == True).all()

try:
    occupied = [r[0] for r in db.query(models.Booking.room_id).filter(
        models.Booking.status.in_([models.BookingStatus.CONFIRMADO, models.BookingStatus.ATIVO]),
        models.Booking.check_out_date > ci,
        models.Booking.check_in_date < co
    ).all()]

    rooms = db.query(models.Room).filter(models.Room.id.notin_(occupied), models.Room.status != models.RoomStatus.MANUTENCAO).all()

    final_rooms = []
    for r in rooms:
        allowed = True
        couple_rule = next((rule for rule in active_rules if rule.name == "Restrição de Casal"), None)
        if couple_rule and group_size == 2:
            restricted_rooms = [rid.strip() for rid in couple_rule.config.get("room_ids", "").split(",") if rid.strip()]
            if r.id in restricted_rooms:
                has_weekend = any((ci + timedelta(days=i)).weekday() in [4, 5, 6] for i in range(days))
                if has_weekend:
                    allowed = False
        if allowed:
            final_rooms.append(r)
    print("SUCCESS: ", [r.id for r in final_rooms])
except Exception as e:
    import traceback
    traceback.print_exc()

