import asyncio
import sys
import os

# Adiciona o diretório backend ao sys.path para importações funcionarem
sys.path.append(os.path.join(os.getcwd()))

from agents.supervisor_agent import SupervisorAgent
from database import SessionLocal, set_tenant_context
import models

async def check_db_history(session_id: str, tenant_id: int):
    db = SessionLocal()
    try:
        set_tenant_context(db, tenant_id)
        msgs = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == session_id).all()
        print(f"\n[DB_CHECK] Mensagens persistidas para {session_id}: {len(msgs)}")
        for m in msgs:
            print(f" - {m.role}: {m.content[:50]}...")
    finally:
        db.close()

async def run_test():
    tenant_id = 1
    session_id = "test_persistence_v1"
    agent = SupervisorAgent(tenant_id)
    
    print("\n=== TURNO 1 ===")
    res1 = await agent.process("Olá, sou o Lucas", session_id)
    print(f"Bot: {res1['response']}")

    print("\n=== TURNO 2 ===")
    res2 = await agent.process("Qual é o meu nome?", session_id)
    print(f"Bot: {res2['response']}")

    await check_db_history(session_id, tenant_id)
    
if __name__ == "__main__":
    asyncio.run(run_test())
