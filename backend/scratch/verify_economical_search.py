import asyncio
import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from agents.graph import pousada_brain

async def test_economical_search():
    print("--- Testando Busca Econômica (Split Inteligente) ---")
    
    session_id = "test_econ_search_001"
    tenant_id = 1
    
    # 4 pessoas, buscando rooms
    print("\n[CENÁRIO] 4 pessoas buscando rooms. Esperamos a opção de 2 quartos de 150 reais.")
    inputs = {
        "message": "Qual a opção mais barata para 4 pessoas nos dias 22 e 23 de abril?",
        "session_id": session_id,
        "tenant_id": tenant_id,
        "context": {
            "check_in": "2026-04-22", 
            "check_out": "2026-04-23", 
            "group_size": 4
        },
        "current_state": "DISCOVERY",
        "next_specialist": "discovery",
        "history": []
    }
    
    result = await pousada_brain.ainvoke(inputs)
    
    print("\nLÓGICA DE DISPONIBILIDADE (PYTHON):")
    availability = result.get("logic_results", {}).get("availability", {})
    
    print("\nOPÇÕES INDIVIDUAIS:")
    for r in availability.get("rooms", []):
        print(f"- {r['room_number']}: R$ {r['total_quote']}")
        
    print("\nOPÇÕES DE COMBINAÇÃO (SPLIT):")
    for c in availability.get("combinations", []):
        print(f"- [{c['strategy'].upper()}] {c['description']} | Total: R$ {c['total_price']}")
    
    print("\nRESPOSTA DA IA:")
    print(result["response"])
    
    # Verificação
    found_cheap = any(c['total_price'] <= 300 for c in availability.get("combinations", []))
    if found_cheap:
        print("\nSUCESSO: A combinação econômica de R$ 300,00 foi encontrada.")
    else:
        print("\nFALHA: A opção de R$ 300,00 não foi apresentada.")

if __name__ == "__main__":
    asyncio.run(test_economical_search())
