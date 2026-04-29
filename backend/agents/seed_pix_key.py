"""
Script para cadastrar a chave PIX de fallback no tenant.
"""
import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal, set_tenant_context
import models

def seed_pix_key(tenant_id: int, pix_key: str):
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)

        # 1. Atualiza/cria o registro em tenant_configs (prioridade do agente)
        config = db.query(models.TenantConfig).filter(
            models.TenantConfig.tenant_id == tenant_id
        ).first()

        if config:
            config.manual_pix_key = pix_key
            print(f"✅ tenant_configs atualizado: manual_pix_key = {pix_key}")
        else:
            config = models.TenantConfig(
                tenant_id=tenant_id,
                manual_pix_key=pix_key,
                is_active=True
            )
            db.add(config)
            print(f"✅ tenant_configs criado com manual_pix_key = {pix_key}")

        # 2. Atualiza/cria também em settings como fallback global
        setting = db.query(models.SystemSetting).filter(
            models.SystemSetting.key == "pousada_pix_key",
            models.SystemSetting.tenant_id == tenant_id
        ).first()

        if setting:
            setting.value = pix_key
            print(f"✅ settings atualizado: pousada_pix_key = {pix_key}")
        else:
            setting = models.SystemSetting(
                key="pousada_pix_key",
                value=pix_key,
                description="Chave PIX manual de fallback para pagamentos via chat",
                tenant_id=tenant_id
            )
            db.add(setting)
            print(f"✅ settings criado: pousada_pix_key = {pix_key}")

        db.commit()
        print(f"\n🎉 Chave PIX '{pix_key}' salva com sucesso para tenant {tenant_id}!")

        # Confirma lendo de volta
        config_check = db.query(models.TenantConfig).filter(
            models.TenantConfig.tenant_id == tenant_id
        ).first()
        setting_check = db.query(models.SystemSetting).filter(
            models.SystemSetting.key == "pousada_pix_key",
            models.SystemSetting.tenant_id == tenant_id
        ).first()

        print("\n📋 CONFIRMAÇÃO:")
        print(f"  tenant_configs.manual_pix_key = {config_check.manual_pix_key if config_check else 'NÃO ENCONTRADO'}")
        print(f"  settings.pousada_pix_key      = {setting_check.value if setting_check else 'NÃO ENCONTRADO'}")

if __name__ == "__main__":
    TENANT_ID = 1
    PIX_KEY = "parceriacomia@pousada.com.br"  # Chave PIX de teste — altere para a real

    print(f"🔑 Cadastrando chave PIX para tenant {TENANT_ID}...")
    seed_pix_key(TENANT_ID, PIX_KEY)
