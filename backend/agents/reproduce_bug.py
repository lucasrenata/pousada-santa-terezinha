import asyncio
import sys
import time
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from agents.supervisor_agent import SupervisorAgent

async def reproduce_loop_bug():
    tenant_id = 1
    # Usa timestamp para garantir sessão 100% limpa a cada execução (sem histórico antigo)
    session_id = f"bug_test_{int(time.time())}"
    supervisor = SupervisorAgent(tenant_id)
    
    print(f"\n🔑 Session ID: {session_id}\n")
    
    print("--- PASSO 1: USUÁRIO JÁ CADASTRADO DIZ 'JA ME CADASTREI' ---")
    # Pré-carrega o contexto com CPF já identificado (simula usuário que passou pelo cadastro)
    supervisor.state_manager.create_session(session_id, {
        "current_state": "DISCOVERY", 
        "cpf": "12345678909", 
        "guest_name": "João Teste",
        "guest_id": 1
    })

    msg1 = "ja me cadastrei"
    res1 = await supervisor.process(msg1, session_id)
    print(f"🤖 IA: {res1['response']}")
    print(f"📍 ESTADO: {res1['state']}\n")

    print("--- PASSO 2: USUÁRIO DÁ AS DATAS LOGO APÓS ---")
    msg2 = "quero dia 25 e 26 de abril, vou sozinho"
    res2 = await supervisor.process(msg2, session_id)
    print(f"👤 USUÁRIO: {msg2}")
    print(f"🤖 IA: {res2['response']}")
    print(f"📍 ESTADO: {res2['state']}")
    
    falhou = "para quando" in res2['response'].lower() or "para quantas" in res2['response'].lower()
    if falhou:
        print("\n❌ FALHA: O agente ainda está repetindo perguntas que já foram respondidas!")
        sys.exit(1)
    else:
        print("\n✅ SUCESSO: O agente reconheceu as datas e avançou o atendimento!")

if __name__ == "__main__":
    asyncio.run(reproduce_loop_bug())
