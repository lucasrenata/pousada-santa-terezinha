from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE rooms ALTER COLUMN maintenance_note TYPE TEXT"))
            conn.commit()
            print("Coluna 'maintenance_note' alterada para TEXT")
        except Exception:
            try:
                conn.execute(text("ALTER TABLE rooms ADD COLUMN maintenance_note TEXT"))
                conn.commit()
                print("Coluna 'maintenance_note' adicionada como TEXT")
            except Exception as e2:
                print(f"Falha na migração: {e2}")

if __name__ == "__main__":
    migrate()
