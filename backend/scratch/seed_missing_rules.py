import sys
import os
from sqlalchemy import text

# Adiciona o diretório atual ao path
sys.path.append("/app")

from database import SessionLocal, set_tenant_context
import models

def seed_rules():
    tenant_id = 1
    db = SessionLocal()
    try:
        set_tenant_context(db, tenant_id)
        
        rules_to_create = [
            {
                "name": "Fim de Semana",
                "description": "Multiplicador de preço para Sexta, Sábado e Domingo",
                "rule_type": "price_modifier",
                "config": {"multiplier": 1.2},
                "is_active": True,
                "tenant_id": tenant_id
            },
            {
                "name": "Estadia Longa",
                "description": "Desconto automático para estadias acima de X dias",
                "rule_type": "discount",
                "config": {"min_days": 7, "discount_percent": 10},
                "is_active": True,
                "tenant_id": tenant_id
            }
        ]

        for rule_data in rules_to_create:
            # Verifica se já existe (para não duplicar se rodar de novo)
            existing = db.query(models.BusinessRule).filter(models.BusinessRule.name == rule_data["name"]).first()
            if not existing:
                print(f"Criando regra: {rule_data['name']}...")
                new_rule = models.BusinessRule(**rule_data)
                db.add(new_rule)
            else:
                print(f"Regra {rule_data['name']} já existe.")
        
        db.commit()
        print("\n✅ Regras de negócio semeadas com sucesso para o Tenant 1!")
        
    except Exception as e:
        print(f"❌ Erro ao semear regras: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_rules()
