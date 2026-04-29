import asyncio
import sys
import json
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from agents.fact_extractor import FactExtractorAgent
from agents.shared_tools import execute_business_logic

async def debug_extraction():
    tenant_id = 1
    extractor = FactExtractorAgent(tenant_id)
    
    msg = "quero dia 25 e 26 de abril vou sozinho"
    context = {"cpf": "39096893883", "guest_name": "lucas cesar guilherme", "guest_id": 1}
    
    print(f"\n🔍 Testando EXTRAÇÃO para: '{msg}'")
    facts = await extractor.extract(msg, context)
    print(f"📦 Fatos extraídos: {json.dumps(facts, indent=2, ensure_ascii=False)}")
    
    print(f"\n⚙️ Testando BUSINESS LOGIC com os fatos...")
    results = await execute_business_logic(tenant_id, msg, {**context, **facts})
    
    up_ctx = results.get("updated_context", {})
    print(f"🔄 Updated Context: {json.dumps(up_ctx, indent=2, ensure_ascii=False)}")
    
    check_in = up_ctx.get("check_in")
    check_out = up_ctx.get("check_out")
    
    if check_in and check_out:
        print(f"\n✅ SUCESSO: Datas detectadas: {check_in} a {check_out}")
    else:
        print(f"\n❌ FALHA: Datas NÃO detectadas!")

if __name__ == "__main__":
    asyncio.run(debug_extraction())
