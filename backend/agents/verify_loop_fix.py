import asyncio
import sys
import json
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from agents.supervisor_agent import SupervisorAgent

async def verify_loop_fix():
    tenant_id = 0 # Using tenant 0 as identified in logs
    session_id = "test_loop_fix_session"
    supervisor = SupervisorAgent(tenant_id)
    
    print(f"\n🚀 Iniciando teste de correção de loop (Tenant {tenant_id})\n")
    
    # Passo 1: CPF
    msg1 = "39096893883"
    print(f"👤 USUÁRIO: {msg1}")
    res1 = await supervisor.process(msg1, session_id)
    print(f"🤖 IA: {res1['response']}")
    print(f"📍 ESTADO: {res1['state']}\n")
    
    # Passo 2: Datas (Onde acontecia o loop)
    msg2 = "quero dia 25 e 26 de abril vou sozinho"
    print(f"👤 USUÁRIO: {msg2}")
    res2 = await supervisor.process(msg2, session_id)
    print(f"🤖 IA: {res2['response']}")
    print(f"📍 ESTADO: {res2['state']}\n")
    
    # Verificação Final
    response_lower = res2['response'].lower()
    loop_indicators = ["para quando", "deseja a reserva", "quantas pessoas"]
    is_looping = any(ind in response_lower for ind in loop_indicators)
    
    if is_looping:
        print("❌ FALHA: O agente AINDA está em loop pedindo datas!")
    else:
        print("✅ SUCESSO: O agente parou de repetir a pergunta e avançou!")
        if res2['state'] == 'VALIDATION' or 'quarto' in response_lower or 'disponiv' in response_lower:
            print("✅ SUCESSO: O agente apresentou opções ou avançou para validação.")

if __name__ == "__main__":
    asyncio.run(verify_loop_fix())
