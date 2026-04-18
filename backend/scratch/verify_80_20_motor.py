import asyncio
import os
import sys

# Ajustar path
sys.path.append(os.getcwd())

from agents.graph import pousada_brain

async def test_80_20_motor():
    print("--- Testando Motor 80/20 (Determinístico) ---")
    
    session_id = "test_80_20_001"
    tenant_id = 1
    
    # 1. TESTE: Solicitação de Disponibilidade e Cotacao de Preco com Sinal
    print("\n[TESTE 1] Solicitação de cotação com sinal de 50%")
    inputs = {
        "message": "Quero reservar o quarto 301 para os dias 22 e 23 de abril para 4 pessoas. Qual o valor pra pagar agora?",
        "session_id": session_id,
        "tenant_id": tenant_id,
        "context": {"group_size": 4},
        "current_state": "DISCOVERY",
        "next_specialist": "discovery",
        "history": []
    }
    
    result = await pousada_brain.ainvoke(inputs)
    
    print("\nCONTEXTO FINAL:")
    print(result.get("context"))
    
    print("\nRESULTADOS DA LÓGICA (PYTHON):")
    logic = result.get("logic_results", {})
    print(f"Preço Total: {logic.get('quote', {}).get('total')}")
    print(f"Informação de Pagamento: {logic.get('payment', {})}")
    
    print("\nRESPOSTA DA IA (20%):")
    print(result["response"])
    
    # Validação
    if logic.get("payment", {}).get("type") == "deposit":
        if logic["payment"]["amount"] == logic["payment"]["total_reserva"] * 0.5:
            print("\nSUCESSO: Cálculo de Sinal (50%) realizado corretamente pelo Python.")
        else:
            print("\nFALHA: Cálculo de sinal incorreto.")

    # 2. TESTE: Pedido de Saldo Restante (Simulando uma reserva parcial existente)
    print("\n[TESTE 2] Pedido de Saldo Restante")
    # Nota: Este teste depende de haver uma reserva parcial no banco. 
    # Para o teste ser isolado, apenas verificamos se a lógica foi chamada.
    inputs_saldo = {
        "message": "Pode me mandar o link do que falta pagar da minha reserva?",
        "session_id": session_id,
        "tenant_id": tenant_id,
        "context": result["context"],
        "current_state": "DISCOVERY",
        "next_specialist": "discovery",
        "history": []
    }
    
    result_saldo = await pousada_brain.ainvoke(inputs_saldo)
    
    print("\nLÓGICA DE SALDO (PYTHON):")
    print(result_saldo.get("logic_results", {}).get("payment"))
    print("\nRESPOSTA DA IA:")
    print(result_saldo["response"])

if __name__ == "__main__":
    asyncio.run(test_80_20_motor())
