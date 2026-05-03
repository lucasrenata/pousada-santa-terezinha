#!/bin/bash
set -e

echo "🚀 [DEPLOY] Iniciando processo de inicialização do sistema..."

# 1. Esperar o Banco de Dados ficar pronto
echo "⏳ Aguardando conexão com o Banco de Dados..."
until python -c "import socket; s = socket.socket(socket.getaddrinfo('db', 5432)[0][0], socket.getaddrinfo('db', 5432)[0][1]); s.connect(('db', 5432)); s.close()" ; do
  echo "😴 Banco ainda dormindo... esperando 2 segundos."
  sleep 2
done

echo "✅ Banco de Dados Online!"

# 2. Executar Migrações do Banco
echo "📦 Checando estado do Banco de Dados..."
python -c "
from database import engine
from sqlalchemy import inspect
import models
inspector = inspect(engine)
if not inspector.has_table('users'):
    print('📦 Banco de dados vazio. Criando tabelas base via SQLAlchemy...')
    models.Base.metadata.create_all(bind=engine)
    import os
    open('/tmp/fresh_db', 'w').close()
else:
    print('📦 Banco de dados já construído previamente. Pulando create_all inicial.')
"

if [ -f /tmp/fresh_db ]; then
    echo "📦 Stamping as migrações do Alembic (Marcando como atualizadas)..."
    alembic stamp head
    rm /tmp/fresh_db
else
    echo "📦 Aplicando migrações do Alembic (head)..."
    alembic upgrade head
fi

# 3. Aplicar Scripts SQL Customizados (Triggers, RLS, etc.)
echo "🛠️ Aplicando scripts SQL customizados de backend/sql/..."
python -c "
import os
from sqlalchemy import text, create_engine

# Usamos a conexão principal do sistema, que possui privilégios de owner do DB no container
admin_url = os.getenv('DATABASE_URL')
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

# 4. Iniciar a aplicação ou comando customizado
if [ "$#" -gt 0 ]; then
    echo "🚀 Executando comando customizado: $@"
    exec "$@"
else
    echo "🚀 Iniciando Uvicorn..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
fi
