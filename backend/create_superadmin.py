import os
import bcrypt
from database import SessionLocal
import models

def create_superadmin():
    db = SessionLocal()
    try:
        # Credenciais Personalizadas solicitadas pelo usuário
        username = "ParcerIA"
        password_plain = "Parc19141919@" 
        
        hashed = bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Verifica se já existe um usuário com esse nome ou se existe o antigo 'superadmin' para migrar
        user = db.query(models.User).filter(models.User.username == username).first()
        
        if user:
            print(f"Usuário {username} já existe. Atualizando status para Super Admin e resetando senha...")
            user.role = "superadmin"
            user.tenant_id = None
            user.password_hash = hashed
        else:
            # Tenta encontrar o 'superadmin' antigo para renomear se for o caso
            old_admin = db.query(models.User).filter(models.User.username == "superadmin").first()
            if old_admin:
                print(f"Migrando usuário antigo 'superadmin' para '{username}'...")
                old_admin.username = username
                old_admin.password_hash = hashed
                old_admin.role = "superadmin"
                old_admin.tenant_id = None
                user = old_admin
            else:
                print(f"Criando novo Administrador Mestre: {username}...")
                user = models.User(
                    username=username,
                    full_name="ParcerIA Master Control",
                    email="admin@parceriacomia.com.br",
                    password_hash=hashed,
                    role="superadmin",
                    tenant_id=None
                )
                db.add(user)

        db.commit()
        print("\n" + "="*40)
        print("🚀 ACESSO MESTRE CONFIGURADO COM SUCESSO!")
        print(f"Usuário: {username}")
        print(f"Senha: {password_plain}")
        print("="*40)
        print("\nPronto para acessar o painel global da plataforma.")
        
    except Exception as e:
        print(f"Erro ao configurar superadmin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_superadmin()
