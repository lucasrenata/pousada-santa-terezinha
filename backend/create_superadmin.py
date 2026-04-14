import os
import bcrypt
from database import SessionLocal
import models

def create_superadmin():
    db = SessionLocal()
    try:
        username = "superadmin"
        # Você pode alterar a senha aqui se desejar antes de rodar na VPS
        password_plain = "admin123" 
        
        hashed = bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        user = db.query(models.User).filter(models.User.username == username).first()
        
        if user:
            print(f"Usuário {username} já existe. Atualizando para Super Admin e resetando senha...")
            user.role = "superadmin"
            user.tenant_id = None # Super Admin não pertence a nenhuma pousada específica
            user.password_hash = hashed
        else:
            print(f"Criando novo Super Admin: {username}...")
            user = models.User(
                username=username,
                full_name="Super Administrador",
                email="admin@pousadasystem.com",
                password_hash=hashed,
                role="superadmin",
                tenant_id=None
            )
            db.add(user)

        db.commit()
        print("\n" + "="*40)
        print("🚀 SUPER ADMIN CRIADO COM SUCESSO!")
        print(f"Usuário: {username}")
        print(f"Senha: {password_plain}")
        print("="*40)
        
    except Exception as e:
        print(f"Erro ao criar superadmin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_superadmin()
