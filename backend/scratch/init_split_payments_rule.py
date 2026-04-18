import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from database import SessionLocal, set_tenant_context
import models

def init_settings(tenant_id: int):
    print(f"--- Inicializando Configurações para Tenant {tenant_id} ---")
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        
        # 1. Configurar Sinal de 50%
        setting = db.query(models.SystemSetting).filter(
            models.SystemSetting.key == "pousada_deposit_percentage",
            models.SystemSetting.tenant_id == tenant_id
        ).first()
        
        if not setting:
            setting = models.SystemSetting(
                key="pousada_deposit_percentage",
                value="50.0",
                description="Porcentagem do sinal para reserva (ex: 50.0). Se vazio, cobra 100%.",
                tenant_id=tenant_id
            )
            db.add(setting)
            print("Configurado sinal de 50.0%")
        else:
            setting.value = "50.0"
            print("Sinal atualizado para 50.0%")
            
        db.commit()
    print("Sucesso!")

if __name__ == "__main__":
    init_settings(1)
