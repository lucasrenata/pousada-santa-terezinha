import sys
import os

# Adiciona o diretório backend ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, set_tenant_context, get_db
import models
import schemas
from sqlalchemy.orm import Session
import uuid

def test_refresh_bug():
    print("Iniciando teste de reprodução do erro de refresh...")
    db = SessionLocal()
    try:
        # 1. Simula um tenant real (ID 1)
        tenant_id = 1
        set_tenant_context(db, tenant_id)
        print(f"Tenant context definido para {tenant_id}")

        # 2. Cria dados do produto
        unique_barcode = f"TEST-{uuid.uuid4().hex[:8]}"
        product_data = {
            "name": "Produto de Teste Fix",
            "price": 10.5,
            "category": "Teste",
            "barcode": unique_barcode,
            "stock_quantity": 10,
            "min_stock": 2
        }
        
        # Simula a lógica do router
        print("Criando instância do produto...")
        new_prod = models.Product(**product_data, tenant_id=tenant_id)
        db.add(new_prod)
        
        # 3. Commit
        print("Executando commit...")
        db.commit()
        print("Commit realizado com sucesso.")

        # 4. Refresh (Onde o erro ocorria)
        print("Tentando executar db.refresh(new_prod)...")
        db.refresh(new_prod)
        print("Refresh realizado com SUCESSO!")
        
        # 5. Teste de UPDATE (Onde o erro persistia)
        print("Iniciando teste de UPDATE...")
        new_prod.name = "Produto de Teste - Editado"
        db.commit()
        print("Commit de update realizado.")
        
        print("Tentando executar db.refresh(new_prod) após UPDATE...")
        db.refresh(new_prod)
        print("Refresh após UPDATE realizado com SUCESSO!")
        
        print(f"Produto Editado: {new_prod.name}")
        
        if new_prod.tenant_id == tenant_id:
            print("VERIFICAÇÃO: tenant_id permanece correto.")
        else:
            print(f"VERIFICAÇÃO FALHOU: tenant_id corrompido")

    except Exception as e:
        print(f"ERRO DURANTE O TESTE: {type(e).__name__}: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_refresh_bug()
