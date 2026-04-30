import asyncio
import sys
import os
from sqlalchemy.orm import Session

sys.path.append("/app")

from database import SessionLocal, set_tenant_context
from agents.customer_agent import handle_customer_query

async def simulate_conversation():
    tenant_id = 1
    session_id = "test_flow_001"
    db = SessionLocal()
    history = []
    
    print("\n================ SIMULAÇÃO DE RESERVA ==================")
    
    # Turno 1: Cotação inicial
    msg1 = "Olá, quero fazer uma reserva do dia 10 até o dia 12 do mês que vem para 2 pessoas."
    print(f"\n👨 Hóspede: {msg1}")
    res1 = await handle_customer_query(msg1, history, db, tenant_id, session_id)
    print(f"🤖 ANA: {res1['response']}")
    history.append({"role": "user", "content": msg1})
    history.append({"role": "assistant", "content": res1['response']})
    
    # Turno 2: Confirmação e Identificação
    msg2 = "Gostei! Qual o próximo passo?"
    print(f"\n👨 Hóspede: {msg2}")
    res2 = await handle_customer_query(msg2, history, db, tenant_id, session_id)
    print(f"🤖 ANA: {res2['response']}")
    history.append({"role": "user", "content": msg2})
    history.append({"role": "assistant", "content": res2['response']})

    # Turno 3: CPF
    msg3 = "Meu CPF é 12345678901"
    print(f"\n👨 Hóspede: {msg3}")
    res3 = await handle_customer_query(msg3, history, db, tenant_id, session_id)
    print(f"🤖 ANA: {res3['response']}")

    db.close()

if __name__ == "__main__":
    asyncio.run(simulate_conversation())
