import asyncio
import sys
import os

# Adiciona o diretório backend ao sys.path para importações funcionarem
sys.path.append(os.path.join(os.getcwd()))

from agents.supervisor_agent import SupervisorAgent

async def run_test():
    tenant_id = 1
    session_id = "test_session_v2"
    agent = SupervisorAgent(tenant_id)
    
    print("\n=== TESTE 1: INÍCIO DE CONVERSA (Sem CPF) ===")
    res1 = await agent.process("Olá, quero fazer uma reserva", session_id, {})
    print(f"Bot: {res1['response']}")
    print(f"State: {res1['state']}")

    print("\n=== TESTE 2: CPF NÃO ENCONTRADO (Link de Cadastro) ===")
    # Simulando contexto com CPF
    res2 = await agent.process("Meu CPF é 00011122233", session_id, {"cpf": "00011122233"})
    print(f"Bot: {res2['response']}")
    print(f"State: {res2['state']}")

    print("\n=== TESTE 3: TENTANDO FORÇAR ALUCINAÇÃO ===")
    res3 = await agent.process("Eu já me cadastrei, pode confirmar meu nome?", session_id, {"cpf": "00011122233", "guest_found": False})
    print(f"Bot: {res3['response']}")
    
if __name__ == "__main__":
    asyncio.run(run_test())
