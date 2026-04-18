import asyncio
import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from agents.specialists.discovery import DiscoverySpecialist

async def test_precision():
    print("--- Testando Precisão do Agente ---")
    s = DiscoverySpecialist(1)
    # Simular pergunta de disponibilidade
    res = await s.process(
        "Quero para os dias 22 e 23/04 para 4 pessoas", 
        "test_sync_precision", 
        {"group_size": 4}
    )
    
    print("\nRESPOSTA DO AGENTE:")
    print(res['response'])
    
    # Verificar se o Quarto 301 tem o preço correto (350) e não o alucinado (300)
    if "350" in res['response'] and "301" in res['response']:
        print("\nSUCESSO: O agente usou os dados REAIS do banco (R$ 350,00).")
    elif "300" in res['response'] or "320" in res['response']:
        print("\nFALHA: O agente ainda está alucinando preços.")
    else:
        print("\nAVISO: Não foi possível identificar o preço na resposta. Verifique manualmente.")

if __name__ == "__main__":
    asyncio.run(test_precision())
