import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal, set_tenant_context
import models

def seed_room(tenant_id: int):
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # Check if any room exists
        room = db.query(models.Room).filter(models.Room.tenant_id == tenant_id).first()
        if not room:
            room = models.Room(
                id="101",
                type="Standard",
                price_per_night=300.0,
                status=models.RoomStatus.DISPONIVEL,
                tenant_id=tenant_id,
                max_capacity=2
            )
            db.add(room)
            db.commit()
            print(f"✅ Quarto 101 (Standard) criado para tenant {tenant_id}")
        else:
            print(f"ℹ️ Quarto já existe: {room.id}")

if __name__ == "__main__":
    seed_room(1)
