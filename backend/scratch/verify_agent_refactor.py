import asyncio
import os
import sys

# Ajustar path para importar módulos do backend
sys.path.append(os.getcwd())

from agents.state_manager import StateManager
from agents.supervisor_agent import SupervisorAgent
from database import SessionLocal, text

async def verify_agent_refactor():
    tenant_id = 1
    session_id = "test_resilience_multi_tenant_01"
    
    print(f"--- Iniciando Verificação para Tenant {tenant_id} ---")
    
    # 1. Testar StateManager UPSERT
    sm = StateManager(tenant_id)
    print("Testando UPSERT no StateManager...")
    res = sm.update_state(session_id, {"check_in": "2026-04-22", "current_state": "DISCOVERY"})
    print(f"Resultado 1: {res}")
    
    # Simular atualização no mesmo ID (deveria dar UniqueViolation sem o fix)
    res2 = sm.update_state(session_id, {"check_out": "2026-04-23"})
    print(f"Resultado 2 (Update): {res2}")
    
    # 2. Verificar se o RLS está isolando (Tentar carregar de outro tenant)
    sm2 = StateManager(2)
    session_from_other = sm2.load_session(session_id)
    print(f"Sessão vista pelo Tenant 2: {session_from_other} (Deveria ser None)")
    
    # 3. Simular uma rodada do Supervisor
    supervisor = SupervisorAgent(tenant_id)
    print("\nSimulando Supervisor...")
    # Mock de mensagem que deveria engatilhar o Discovery -> Validation
    # Mas como não temos LLM aqui facilmente sem keys, vamos apenas testar a persistência do supervisor
    response = await supervisor.process("Quero o quarto 301", session_id)
    print(f"Estado após processamento: {response['state']}")
    print(f"Contexto salvo: {response['context']}")

if __name__ == "__main__":
    asyncio.run(verify_agent_refactor())
