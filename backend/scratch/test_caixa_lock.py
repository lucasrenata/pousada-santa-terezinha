import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, set_tenant_context
import models
from jose import jwt
from datetime import datetime, timedelta
from routers.auth import SECRET_KEY, ALGORITHM

client = TestClient(app)

def get_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode = {"sub": username, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def setup_users_and_tenant():
    db = SessionLocal()
    try:
        set_tenant_context(db, -1)
        
        # 1. Tenant
        tenant = db.query(models.Tenant).filter(models.Tenant.id == 1).first()
        if not tenant:
            tenant = models.Tenant(id=1, name="Pousada Teste", is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            
        # 2. Admin User
        admin = db.query(models.User).filter(models.User.username == "admin_test").first()
        if not admin:
            admin = models.User(
                username="admin_test",
                email="admin_test@example.com",
                full_name="Gerente Teste",
                role="admin",
                password_hash="mock",
                tenant_id=1
            )
            db.add(admin)
            
        # 3. Receptionist User
        recep = db.query(models.User).filter(models.User.username == "recep_test").first()
        if not recep:
            recep = models.User(
                username="recep_test",
                email="recep_test@example.com",
                full_name="Operador Teste",
                role="recepcionista",
                password_hash="mock",
                tenant_id=1
            )
            db.add(recep)
            db.commit()
            db.refresh(recep)
            
        # 4. Clear existing open sessions for recep_test
        open_sessions = db.query(models.CaixaSession).filter(
            models.CaixaSession.user_id == recep.id,
            models.CaixaSession.status == models.CaixaStatus.ABERTO
        ).all()
        for session in open_sessions:
            db.query(models.CaixaMovement).filter(models.CaixaMovement.session_id == session.id).delete()
            db.delete(session)
        
        db.commit()
    finally:
        db.close()

def run_tests():
    print("START: Iniciando Testes de Fechamento de Caixa Blindado...")
    setup_users_and_tenant()
    
    admin_token = get_token("admin_test")
    recep_token = get_token("recep_test")
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_recep = {"Authorization": f"Bearer {recep_token}"}
    
    # --- TESTE 1: Configurar o PIN do gerente ---
    print("\n--- TESTE 1: Configurar o PIN do gerente ---")
    payload_pin = {
        "key": "caixa_pin",
        "value": "9876",
        "description": "PIN de autorizacao"
    }
    res = client.post("/settings/", json=payload_pin, headers=headers_admin)
    assert res.status_code == 200, f"Falha ao configurar PIN: {res.text}"
    print("OK: PIN configurado com sucesso para '9876'")

    # --- TESTE 2: Operador abre o caixa ---
    print("\n--- TESTE 2: Operador abre o caixa ---")
    payload_open = {
        "opening_balance": 150.0
    }
    res = client.post("/pdv/caixa/abrir", json=payload_open, headers=headers_recep)
    assert res.status_code == 200, f"Falha ao abrir caixa: {res.text}"
    session_id = res.json()["id"]
    print(f"OK: Caixa aberto com ID {session_id} e saldo inicial R$ 150,00")

    # Adicionar vendas e movimentações (uma venda em dinheiro, uma em pix, uma sangria)
    db = SessionLocal()
    try:
        set_tenant_context(db, 1)
        # Venda Dinheiro: R$ 50,00
        m1 = models.CaixaMovement(
            session_id=session_id,
            type=models.CaixaMovementType.VENDA,
            amount=50.0,
            description="Venda Comanda #1",
            payment_method=models.PaymentMethod.DINHEIRO,
            tenant_id=1
        )
        # Venda PIX: R$ 80,00
        m2 = models.CaixaMovement(
            session_id=session_id,
            type=models.CaixaMovementType.VENDA,
            amount=80.0,
            description="Venda Comanda #2",
            payment_method=models.PaymentMethod.PIX,
            tenant_id=1
        )
        # Sangria Dinheiro: R$ 20,00
        m3 = models.CaixaMovement(
            session_id=session_id,
            type=models.CaixaMovementType.SANGRIA,
            amount=20.0,
            description="Retirada Troco",
            tenant_id=1
        )
        db.add_all([m1, m2, m3])
        db.commit()
    finally:
        db.close()
    
    # Saldo Esperado em Dinheiro = 150 (abertura) + 50 (venda dinheiro) - 20 (sangria) = R$ 180,00

    # --- TESTE 3: Operador solicita o Resumo de Caixa (Verificar Redação Blindada) ---
    print("\n--- TESTE 3: Verificar redacao blindada para o Operador ---")
    res = client.get("/pdv/caixa/summary", headers=headers_recep)
    assert res.status_code == 200, f"Falha ao obter summary: {res.text}"
    summary = res.json()
    
    # Operador não deve ver detalhes de dinheiro
    assert summary["vendas_dinheiro"] == 0.0, "Operador viu vendas_dinheiro!"
    assert summary["entradas_total"] == 0.0, "Operador viu suprimentos!"
    assert summary["retiradas_total"] == 0.0, "Operador viu sangrias!"
    assert summary["saldo_dinheiro"] == 0.0, "Operador viu saldo_dinheiro!"
    
    # Outros métodos de recebimento e total geral (que só inclui outros métodos) devem aparecer
    assert summary["vendas_pix"] == 80.0, "Operador nao viu PIX!"
    assert summary["saldo_geral"] == 80.0, f"Saldo geral incorreto para operador: {summary['saldo_geral']}"
    
    # Movimentações em dinheiro devem ser ocultadas da listagem
    movements = summary["movements"]
    for m in movements:
        assert m["type"] not in ["SUPRIMENTO", "SANGRIA", "RETIRADA"], "Operador viu movimento de sangria/suprimento!"
        if m["type"] == "VENDA":
            assert m["payment_method"] != "DINHEIRO", "Operador viu movimento de venda em dinheiro!"
            
    print("OK: Redacao blindada do resumo para recepcionista validada com sucesso!")

    # --- TESTE 4: Fechamento com Divergência sem PIN (Deve falhar) ---
    print("\n--- TESTE 4: Fechamento com divergencia fisica sem PIN ---")
    # Saldo esperado em dinheiro é 180. Fechando com 175.
    res = client.post("/pdv/caixa/fechar?closing_balance=175.00", headers=headers_recep)
    assert res.status_code == 400, f"Devia ter bloqueado por divergencia! Codigo: {res.status_code}"
    assert "Caixa faltando R$ 5,00" in res.json()["detail"], f"Mensagem inesperada: {res.json()}"
    print("OK: Bloqueio de divergencia sem PIN funcionando.")

    # --- TESTE 5: Fechamento com Divergência e PIN Incorreto (Deve falhar) ---
    print("\n--- TESTE 5: Fechamento com divergencia e PIN incorreto ---")
    res = client.post("/pdv/caixa/fechar?closing_balance=175.00&manager_pin=1111", headers=headers_recep)
    assert res.status_code == 400, f"Devia ter rejeitado por PIN incorreto! Codigo: {res.status_code}"
    assert "gerente incorreto" in res.json()["detail"]
    print("OK: Rejeicao de PIN incorreto funcionando.")

    # --- TESTE 6: Fechamento com Divergência e PIN Correto (Deve passar) ---
    print("\n--- TESTE 6: Fechamento com divergencia e PIN correto ---")
    res = client.post("/pdv/caixa/fechar?closing_balance=175.00&manager_pin=9876", headers=headers_recep)
    assert res.status_code == 200, f"Deveria ter fechado com sucesso usando o PIN correto! {res.text}"
    session_data = res.json()
    assert session_data["status"] == "fechado", "Status da sessao deveria ser FECHADO"
    assert session_data["summary_json"]["manager_authorized"] is True, "Gerente nao foi registrado como autorizador!"
    assert session_data["summary_json"]["divergence_amount"] == -5.0, "Valor da divergencia nao gravado corretamente!"
    print("OK: Fechamento com PIN do gerente concluido com sucesso!")

    print("\nSUCCESS: TODOS OS TESTES PASSARAM COM SUCESSO! SUCCESS")

if __name__ == "__main__":
    run_tests()
