from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def seed_data():
    db = SessionLocal()
    try:
        # 1. Create Default Admin
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_user:
            print("Criando usuário admin padrão...")
            admin_user = models.User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin_user)
        
        # 2. Create Default Settings
        default_settings = [
            {"key": "pousada_rate_child_percentage", "value": "50", "description": "Porcentagem da diária para crianças de 7-12 anos"},
            {"key": "pousada_rate_infant_fixed", "value": "25", "description": "Valor fixo diário para crianças de 0-6 anos"},
            {"key": "pousada_name", "value": "Estabelecimento", "description": "Nome oficial do estabelecimento (ex: Hotel, Pousada, Hostel)"},
            {"key": "pousada_phone", "value": "(11) 99999-9999", "description": "Telefone de contato público"}
        ]
        
        for s in default_settings:
            exists = db.query(models.SystemSetting).filter(models.SystemSetting.key == s["key"]).first()
            if not exists:
                print(f"Criando configuração: {s['key']}...")
                db.add(models.SystemSetting(**s))

        # 3. Create Default Rooms
        rooms = [
            {"id": "101", "type": "Standard", "price_per_night": 150.0, "max_capacity": 2},
            {"id": "102", "type": "Standard", "price_per_night": 150.0, "max_capacity": 2},
            {"id": "201", "type": "Luxo", "price_per_night": 250.0, "max_capacity": 3},
            {"id": "202", "type": "Luxo", "price_per_night": 250.0, "max_capacity": 3},
            {"id": "400", "type": "Master VIP", "price_per_night": 450.0, "max_capacity": 4},
        ]
        for r in rooms:
            exists = db.query(models.Room).filter(models.Room.id == r["id"]).first()
            if not exists:
                print(f"Criando quarto: {r['id']}...")
                db.add(models.Room(**r))
        
        db.commit()
        print("Seed finalizado com sucesso! 🚀")
        
    except Exception as e:
        print(f"Erro no seed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
