import sys
import asyncio
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from routers.chat import run_admin_task, run_agent_task
import time

def test_persistence():
    session_id = f"test_persist_{int(time.time())}"
    tenant_id = 0
    print(f"\n🧪 [TESTE] Iniciando Sessão de Teste: {session_id}")

    # TESTE 1: Customer Agent
    print("\n--- TESTE 1: Customer Agent (Atendente) ---")
    print("Enviando mensagem: 'Olá, meu nome é Sr. Teste Silva'")
    res1 = run_agent_task("Olá, meu nome é Sr. Teste Silva", session_id, tenant_id)
    print(f"🤖 Resposta 1: {res1.get('response')}")
    
    print("\n[Aguardando 1 segundo para o banco gravar...]")
    time.sleep(1)
    
    print("Enviando mensagem: 'Qual é o meu nome?'")
    res2 = run_agent_task("Qual é o meu nome?", session_id, tenant_id)
    print(f"🤖 Resposta 2: {res2.get('response')}")
    if "Teste Silva" in res2.get('response', ''):
        print("✅ SUCESSO: Memória do Customer Agent está funcionando perfeitamente!")
    else:
        print("❌ FALHA: O Customer Agent esqueceu o nome.")

    # TESTE 2: Admin Agent
    print("\n--- TESTE 2: Admin Agent (Administrativo) ---")
    admin_session = f"admin_{session_id}"
    print("Enviando comando: 'Quais os eventos da Canção Nova em maio de 2026?'")
    res_admin = run_admin_task("Quais os eventos da Canção Nova em maio de 2026?", [], tenant_id, admin_session)
    print(f"🤖 Resposta Admin 1: {res_admin.get('response')}")
    if "Aprofundamento" in res_admin.get('response', '') or "Acampamento" in res_admin.get('response', ''):
        print("✅ SUCESSO: Robô de Eventos funcionando e listando Maio/2026!")
    else:
        print("❌ FALHA: Robô de Eventos não encontrou ou não foi chamado.")

    print("\n[Aguardando 1 segundo...]")
    time.sleep(1)
    
    print("Enviando pergunta solta: 'Quais eram mesmos?'")
    res_admin2 = run_admin_task("Quais eram mesmos?", [], tenant_id, admin_session)
    print(f"🤖 Resposta Admin 2: {res_admin2.get('response')}")
    if "Aprofundamento" in res_admin2.get('response', '') or "Acampamento" in res_admin2.get('response', ''):
        print("✅ SUCESSO: Memória do Admin Agent ativada, ele lembrou do contexto!")
    else:
        print("❌ FALHA: O Admin Agent esqueceu o relatório gerado.")

if __name__ == "__main__":
    test_persistence()
