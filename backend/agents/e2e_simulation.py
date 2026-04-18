import asyncio
import os
import sys
from pathlib import Path

# Adicionar o diretório backend ao sys.path
backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from database import SessionLocal
from agents.supervisor_agent import SupervisorAgent
import models

async def run_e2e_simulation():
    """
    Simula uma jornada completa de um hóspede:
    1. Saudação / Descoberta (Busca datas)
    2. Seleção de Quarto (Confirma intenção)
    3. Identificação (CPF)
    4. Acompanhantes (Dados extras)
    5. Confirmação Final (Resumo)
    6. Pagamento (Geração de PIX)
    """
    
    print("\n" + "="*60)
    print("🚀 INICIANDO SIMULAÇÃO E2E: MULTI-AGENT RESERVATION")
    print("="*60 + "\n")
    
    db = SessionLocal()
    tenant_id = 1 # ID padrão para testes
    from database import set_tenant_context
    set_tenant_context(db, tenant_id)
    session_id = "e2e_forensic_test"
    
    # Garantir que o hóspede de teste existe
    test_cpf = "12345678909"
    guest = db.query(models.Guest).filter(models.Guest.document == test_cpf).first()
    if not guest:
        print(f"🌱 Semeando hóspede de teste ({test_cpf})...")
        guest = models.Guest(
            name="João Simulação",
            document=test_cpf,
            email="joao@teste.com",
            tenant_id=tenant_id
        )
        db.add(guest)
        db.commit()
    
    supervisor = SupervisorAgent(tenant_id)
    
    # Roteiro da Conversa
    interchanges = [
        ("Olá! Tem vaga para o dia 15 de maio até 17 de maio?", "DISCOVERY"),
        ("Quanto custa?", "DISCOVERY"),
        ("Perfeito, quero reservar este quarto para 2 pessoas.", "VALIDATION"),
        ("Meu CPF é 123.456.789-00", "VALIDATION"), # Nota: Use um CPF válido se o Módulo 11 estiver ativo. 123.456.789-00 é inválido.
        # Simulando um CPF válido (ex: 12345678909)
        ("Meu CPF é 12345678909", "VALIDATION"),
        ("Vou com minha esposa, Maria Silva, ela tem 30 anos.", "VALIDATION"),
        ("Sim, as informações estão corretas. Pode prosseguir.", "CONFIRMATION"),
        ("Ok, como eu pago agora?", "PAYMENT"),
        ("Já paguei!", "COMPLETE")
    ]
    
    try:
        for i, (user_msg, expected_state) in enumerate(interchanges):
            print(f"👤 [HÓSPEDE]: {user_msg}")
            
            # Processar mensagem
            result = await supervisor.process(user_msg, session_id)
            
            response = result.get('response', '...')
            state = result.get('state', 'UNKNOWN')
            spec = result.get('specialist', 'none')
            
            print(f"🤖 [IA - {spec.upper()}]: {response}")
            print(f"📍 [ESTADO]: {state}")
            print("-" * 40)
            
            # Pequeno delay para legibilidade
            await asyncio.sleep(1)
            
            if state == "COMPLETE":
                print("\n✅ SIMULAÇÃO CONCLUÍDA COM SUCESSO!")
                break
                
    except Exception as e:
        print(f"\n❌ ERRO NA SIMULAÇÃO: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        print("\n" + "="*60)
        print("🏁 FIM DA SIMULAÇÃO")
        print("="*60 + "\n")

if __name__ == "__main__":
    # Garantir que temos as chaves necessárias (pelo menos mocks se não houver reais)
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("⚠️ AVISO: Nenhuma chave de API de IA configurada (.env). O teste pode falhar.")
    
    asyncio.run(run_e2e_simulation())
