#!/bin/bash
set -e

echo "🚀 [DEPLOY] Iniciando processo de inicialização do sistema..."

# 1. Esperar o Banco de Dados ficar pronto
echo "⏳ Aguardando conexão com o Banco de Dados..."
until python -c "import socket; s = socket.socket(socket.getaddrinfo('pousada_db', 5432)[0][0], socket.getaddrinfo('pousada_db', 5432)[0][1]); s.connect(('pousada_db', 5432)); s.close()" ; do
  echo "😴 Banco ainda dormindo... esperando 2 segundos."
  sleep 2
done

echo "✅ Banco de Dados Online!"

# 2. Executar Migrações do Alembic (Tabelas e Índices)
echo "📦 Aplicando migrações do Alembic (head)..."
alembic upgrade head

# 3. Aplicar Scripts SQL Customizados (Triggers, RLS, etc.)
echo "🛠️ Aplicando scripts SQL customizados de backend/sql/..."
python -c "
import os
from sqlalchemy import text, create_engine

# Usamos a conexão de ADMIN para garantir privilégios de ALTER TABLE e TRIGGER
admin_url = 'postgresql://admin:admin_password_123@pousada_db:5432/pousada_db'
engine = create_engine(admin_url)

sql_dir = 'sql'
if os.path.exists(sql_dir):
    files = sorted([f for f in os.listdir(sql_dir) if f.endswith('.sql')])
    for filename in files:
        print(f'   -> Executando: {filename}')
        with open(os.path.join(sql_dir, filename), 'r') as f:
            sql = f.read()
            try:
                with engine.connect() as conn:
                    # Bypassa RLS para configuração global
                    conn.execute(text(\"SET app.current_tenant = '-1'\"))
                    conn.execute(text(sql))
                    conn.commit()
            except Exception as e:
                print(f'      ❌ Erro em {filename}: {e}')
else:
    print('   ! Canal SQL não encontrado, pulando.')
"

echo "✨ [SUCCESS] Deploy do banco concluído!"

# 4. Iniciar a aplicação
echo "🚀 Iniciando Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers
