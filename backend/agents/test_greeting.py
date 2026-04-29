import asyncio
import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from agents.supervisor_agent import SupervisorAgent

async def test_personalized_greeting():
    tenant_id = 1
    session_id = "test_greeting_session"
    supervisor = SupervisorAgent(tenant_id)
    
    print(f"\n🔑 Testando saudação personalizada para CPF: 39096893883\n")
    
    # 1. Enviar o CPF
    msg = "39096893883"
    print(f"👤 USUÁRIO: {msg}")
    res = await supervisor.process(msg, session_id)
    print(f"🤖 IA: {res['response']}")
    print(f"📍 ESTADO: {res['state']}")
    
    if "lucas" in res['response'].lower():
        print("\n✅ SUCESSO: O agente identificou o hóspede pelo nome!")
    else:
        print("\n❌ FALHA: O agente NÃO usou o nome do hóspede na resposta.")

if __name__ == "__main__":
    asyncio.run(test_personalized_greeting())
