import asyncio
import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from agents.graph import pousada_brain

async def test_cpf_barrier():
    print("--- Testando Barreira de CPF (Integridade de Fluxo) ---")
    
    session_id = "test_cpf_barrier_001"
    tenant_id = 1
    
    # Simular seleção de quarto 301 (sem guest_id no contexto)
    print("\n[CENÁRIO] Hóspede seleciona quarto, mas não informou CPF ainda.")
    inputs = {
        "message": "Quero o quarto 301",
        "session_id": session_id,
        "tenant_id": tenant_id,
        "context": {
            "check_in": "2026-04-22", 
            "check_out": "2026-04-23", 
            "group_size": 4,
            "room_id": "301" # Já extraído pelo guardian
        },
        "current_state": "DISCOVERY",
        "next_specialist": "discovery",
        "history": []
    }
    
    result = await pousada_brain.ainvoke(inputs)
    
    print("\nRESPOSTA DA IA:")
    print(result["response"])
    
    # Verificação
    resp_lower = result["response"].lower()
    if "cpf" in resp_lower or "cadastro" in resp_lower:
        print("\nSUCESSO: O agente barrou o fluxo e pediu o CPF corretamente.")
    else:
        print("\nFALHA: O agente ignorou a barreira e tentou prosseguir sem CPF.")

if __name__ == "__main__":
    asyncio.run(test_cpf_barrier())
