import sys
import asyncio
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from agents.supervisor_agent import SupervisorAgent
from agents.admin_agent import handle_admin_query
from database import SessionLocal
import time

async def main():
    session_id = f"test_persist_{int(time.time())}"
    tenant_id = 0
    print(f"\n🧪 [TESTE] Iniciando Sessão de Teste: {session_id}")

    # TESTE 1: Customer Agent
    print("\n--- TESTE 1: Customer Agent (Atendente) ---")
    supervisor = SupervisorAgent(tenant_id)
    print("Enviando mensagem: 'Olá, meu nome é Sr. Teste Silva'")
    res1 = await supervisor.process("Olá, meu nome é Sr. Teste Silva", session_id)
    print(f"🤖 Resposta 1: {res1.get('response')}")
    
    print("\n[Aguardando 1 segundo para o banco gravar...]")
    await asyncio.sleep(1)
    
    print("Enviando mensagem: 'Qual é o meu nome?'")
    res2 = await supervisor.process("Qual é o meu nome?", session_id)
    print(f"🤖 Resposta 2: {res2.get('response')}")
    if "Teste Silva" in res2.get('response', ''):
        print("✅ SUCESSO: Memória do Customer Agent está funcionando perfeitamente!")
    else:
        print("❌ FALHA: O Customer Agent esqueceu o nome.")

    # TESTE 2: Admin Agent
    print("\n--- TESTE 2: Admin Agent (Administrativo) ---")
    admin_session = f"admin_{session_id}"
    db = SessionLocal()
    
    print("Enviando comando: 'Quais os eventos da Canção Nova em maio de 2026?'")
    res_admin = await handle_admin_query("Quais os eventos da Canção Nova em maio de 2026?", [], db, tenant_id, admin_session)
    print(f"🤖 Resposta Admin 1: {res_admin.get('response')}")
    
    print("\n[Aguardando 1 segundo...]")
    await asyncio.sleep(1)
    
    print("Enviando pergunta solta: 'Quais eram mesmos?'")
    res_admin2 = await handle_admin_query("Quais eram mesmos?", [], db, tenant_id, admin_session)
    print(f"🤖 Resposta Admin 2: {res_admin2.get('response')}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
