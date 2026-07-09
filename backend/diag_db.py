import os
from sqlalchemy import create_engine, text
from database import SessionLocal
import models

def diag():
    print("--- DIAGNOSTICO DE BANCO ---")
    url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {url}")
    
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # 1. Tabelas
            tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
            print(f"Tabelas encontradas: {[t[0] for t in tables]}")
            
            # 2. Usuarios
            users = conn.execute(text("SELECT id, username, role, tenant_id FROM users")).fetchall()
            print(f"Usuarios ({len(users)}):")
            for u in users:
                print(f"  - ID: {u[0]}, User: {u[1]}, Role: {u[2]}, Tenant: {u[3]}")
            
            # 3. Tenants
            tenants = conn.execute(text("SELECT id, name FROM tenants")).fetchall()
            print(f"Tenants ({len(tenants)}):")
            for t in tenants:
                print(f"  - ID: {t[0]}, Name: {t[1]}")
                
            # 4. Settings (Global)
            settings = conn.execute(text("SELECT count(*) FROM settings")).scalar()
            print(f"Settings total: {settings}")

    except Exception as e:
        print(f"ERRO: {e}")

if __name__ == "__main__":
    diag()
