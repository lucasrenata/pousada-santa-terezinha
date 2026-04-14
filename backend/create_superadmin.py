import os
import bcrypt
from database import SessionLocal, set_tenant_context
import models
from datetime import datetime

def create_superadmin():
    db = SessionLocal()
    try:
        # Ativa visão global para o script
        set_tenant_context(db, -1)
        # 1. Garante a existência do Tenant Mestre (Plataforma)
        platform_tenant = db.query(models.Tenant).filter(models.Tenant.name == "ParcerIA (Plataforma)").first()
        if not platform_tenant:
            print("Criando Tenant Mestre: ParcerIA (Plataforma)...")
            platform_tenant = models.Tenant(
                name="ParcerIA (Plataforma)",
                subdomain="parceria",
                is_active=True,
                created_at=datetime.now()
            )
            db.add(platform_tenant)
            db.commit()
            db.refresh(platform_tenant)
        
        # 2. Credenciais Personalizadas
        username = "ParcerIA"
        password_plain = "Parc19141919@" 
        hashed = bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 3. Gerenciamento do Usuário
        user = db.query(models.User).filter(models.User.username == username).first()
        
        if user:
            print(f"Usuário {username} já existe. Vinculando ao Tenant da Plataforma e resetando senha...")
            user.role = "superadmin"
            user.tenant_id = platform_tenant.id
            user.password_hash = hashed
        else:
            # Tenta encontrar o 'superadmin' antigo para renomear
            old_admin = db.query(models.User).filter(models.User.username == "superadmin").first()
            if old_admin:
                print(f"Migrando usuário antigo 'superadmin' para '{username}' e vinculando à plataforma...")
                old_admin.username = username
                old_admin.password_hash = hashed
                old_admin.role = "superadmin"
                old_admin.tenant_id = platform_tenant.id
                user = old_admin
            else:
                print(f"Criando novo Administrador Mestre: {username}...")
                user = models.User(
                    username=username,
                    full_name="ParcerIA Master Control",
                    email="admin@parceriacomia.com.br",
                    password_hash=hashed,
                    role="superadmin",
                    tenant_id=platform_tenant.id
                )
                db.add(user)

        db.commit()
        print("\n" + "="*40)
        print("🚀 CONTA PLATAFORMA CONFIGURADA!")
        print(f"Usuário: {username}")
        print(f"Tenant Vinculado: {platform_tenant.name} (ID: {platform_tenant.id})")
        print("="*40)
        
    except Exception as e:
        print(f"Erro ao configurar conta plataforma: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_superadmin()
