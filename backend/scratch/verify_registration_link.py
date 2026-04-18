import asyncio
import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from agents.graph import pousada_brain

async def test_registration_link():
    print("--- Testando Entrega de Link de Cadastro ---")
    
    session_id = "test_reg_link_001"
    tenant_id = 1
    
    # Simular CPF inexistente
    print("\n[CENÁRIO] Hóspede informa CPF que NÃO está no banco.")
    inputs = {
        "message": "Meu CPF é 123.456.789-00",
        "session_id": session_id,
        "tenant_id": tenant_id,
        "context": {
            "check_in": "2026-04-22", 
            "check_out": "2026-04-23", 
            "group_size": 4,
            "room_id": "301",
            "cpf": "123.456.789-00" # Simula que o guardian já extraiu
        },
        "current_state": "DISCOVERY",
        "next_specialist": "discovery",
        "history": []
    }
    
    result = await pousada_brain.ainvoke(inputs)
    
    print("\nLÓGICA DE BUSCA (PYTHON):")
    print(result.get("logic_results", {}).get("guest"))
    
    print("\nRESPOSTA DA IA:")
    print(result["response"])
    
    # Verificação
    resp_lower = result["response"].lower()
    if "link" in resp_lower or "cadastro" in resp_lower or "formulario" in resp_lower:
        print("\nSUCESSO: O agente forneceu o link de cadastro corretamente.")
    else:
        print("\nFALHA: O agente não deu o link.")

if __name__ == "__main__":
    asyncio.run(test_registration_link())
