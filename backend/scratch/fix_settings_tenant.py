import sys
import os
from sqlalchemy import text

# Adiciona o diretório atual ao path
sys.path.append("/app")

from database import SessionLocal
import models

def fix_settings():
    db = SessionLocal()
    try:
        # Busca configurações sem tenant ou com tenant 0
        orphan_settings = db.execute(text('SELECT id, key, value, description FROM settings WHERE tenant_id IS NULL OR tenant_id = 0')).all()
        
        for s_id, s_key, s_val, s_desc in orphan_settings:
            # Verifica se já existe para o Tenant 1
            existing = db.execute(text('SELECT id FROM settings WHERE key = :key AND tenant_id = 1'), {'key': s_key}).first()
            
            if not existing:
                print(f"Recuperando: {s_key} -> Tenant 1")
                db.execute(text('UPDATE settings SET tenant_id = 1 WHERE id = :id'), {'id': s_id})
            else:
                print(f"Removendo duplicata: {s_key} (já existe no Tenant 1)")
                db.execute(text('DELETE FROM settings WHERE id = :id'), {'id': s_id})
        
        db.commit()
        print("\n✅ Todas as configurações foram normalizadas para o Tenant 1!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_settings()
