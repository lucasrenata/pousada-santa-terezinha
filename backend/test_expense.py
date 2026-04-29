import asyncio
from database import SessionLocal, engine, Base
import models
from agents.admin_agent import handle_admin_query
import sys

async def run_test():
    db = SessionLocal()
    tenant = db.query(models.Tenant).first()
    if not tenant:
        print("Criando tenant de teste...")
        tenant = models.Tenant(name="Pousada Teste")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    
    tenant_id = tenant.id
    message = "Lan\u00e7a uma despesa de R$ 150 para conserto de telhado hoje"
    history = []
    print(f"Enviando mensagem ao agente: {message}")
    
    try:
        result = await handle_admin_query(message, history, db, tenant_id, "test_session_123")
        print("\n=== RESPOSTA DO AGENTE ===")
        print(result.get("response"))
        
        # Verificar o banco de dados
        print("\n=== VERIFICANDO BD ===")
        expense = db.query(models.Expense).order_by(models.Expense.id.desc()).first()
        if expense:
            print(f"ID: {expense.id}")
            print(f"Descri\u00e7\u00e3o: {expense.description}")
            print(f"Valor: R$ {expense.amount}")
            print(f"Categoria: {expense.category.value if hasattr(expense.category, 'value') else expense.category}")
            print(f"Pago: {expense.is_paid}")
            print("SUCESSO: A despesa foi lan\u00e7ada no banco!")
        else:
            print("FALHA: Nenhuma despesa nova encontrada.")
            
    except Exception as e:
        print(f"Erro durante a execu\u00e7\u00e3o: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
