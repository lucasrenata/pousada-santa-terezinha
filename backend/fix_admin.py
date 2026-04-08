import bcrypt
from database import SessionLocal
import models

def fix():
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        password_plain = "admin123"
        hashed = bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        if admin:
            print(f"Atualizando hash para {admin.username}...")
            admin.password_hash = hashed
        else:
            print("Criando admin principal...")
            admin = models.User(username="admin", password_hash=hashed, role="admin")
            db.add(admin)

        db.commit()
        print("ADMIN FIX SUCCESS! 🚀")
    finally:
        db.close()

if __name__ == "__main__":
    fix()
