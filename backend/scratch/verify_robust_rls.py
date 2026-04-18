
import sys
import os
import time

# Adiciona o diretório backend ao path para importar os módulos
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from database import SessionLocal, set_tenant_context, text
import models

def verify_robust_rls():
    print("Iniciando verificação robusta de RLS...")
    tenant_id = 1
    session_id = f"test_robust_{int(time.time())}"
    
    # 1. Abrir sessão e configurar contexto inicial
    db = SessionLocal()
    try:
        print(f"Configurando tenant_id = {tenant_id} na sessão...")
        set_tenant_context(db, tenant_id)
        
        # 2. Primeira Operação (Insert do Usuário)
        print("Executando primeira operação (User Message)...")
        msg1 = models.ChatMessage(
            session_id=session_id,
            role='user',
            content="Olá, teste 1",
            tenant_id=tenant_id
        )
        db.add(msg1)
        db.commit()
        print("Primeiro commit realizado com sucesso.")
        
        # 3. Simular atraso (onde antes o contexto se perdia)
        print("Simulando espera de processamento (2 segundos)...")
        time.sleep(2)
        
        # 4. Segunda Operação (Insert da IA - Onde o erro ocorria)
        # Aqui, no modelo antigo, a conexão poderia ter sido resetada. 
        # Com o novo hook after_begin, o contexto deve ser restaurado automaticamente.
        print("Executando segunda operação (Assistant Message)...")
        msg2 = models.ChatMessage(
            session_id=session_id,
            role='assistant',
            content="Olá! Sou a IA e este é o teste 2 robusto.",
            tenant_id=tenant_id
        )
        db.add(msg2)
        db.commit()
        print("Segundo commit realizado com SUCESSO!")
        
        # 5. Verificação Final via Consulta
        print("Verificando se as mensagens estão visíveis para o tenant...")
        results = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == session_id
        ).all()
        
        if len(results) == 2:
            print(f"VERIFICAÇÃO CONCLUÍDA: {len(results)} mensagens encontradas.")
            print("TESTE ROBUSTO PASSOU!")
        else:
            print(f"VERIFICAÇÃO FALHOU: Apenas {len(results)} mensagens encontradas.")

    except Exception as e:
        print(f"ERRO DURANTE O TESTE: {type(e).__name__}: {e}")
        # Se falhou, vamos ver qual era o estado do app.current_tenant se possível
        try:
            res = db.execute(text("SHOW app.current_tenant")).fetchone()
            print(f"Estado de app.current_tenant no erro: {res}")
        except: pass
    finally:
        db.close()

if __name__ == "__main__":
    verify_robust_rls()
