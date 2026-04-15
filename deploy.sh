#!/bin/bash

echo "🚀 Iniciando deployment da Pousada System na VPS..."

# 1. Derruba os containers antigos
echo "🛑 Parando containers antigos..."
docker compose down

# 2. Recria imagens com as novas variáveis e atualizações de código
echo "🏗️ Construindo novas imagens..."
docker compose build --no-cache

# 3. Sobe todos os containers em background
echo "🟢 Subindo containers em background..."
docker compose up -d

# 4. Aguarda o Postgres e o Backend inicializarem
echo "⏳ Aguardando os serviços iniciarem (15s)..."
sleep 15

# 5. Re-provisiona permissões do banco via peer auth (usuário interno do container)
# Usa '-u postgres' para autenticar via peer auth sem precisar de senha.
# Isso garante acesso de superuser independente de quem criou as tabelas.
echo "🔑 Provisionando permissões do banco de dados..."
docker exec -u postgres pousada_db psql -d pousada_db -c "
  -- Transfere ownership de todas as tabelas existentes para pousada_app
  DO \$\$
  DECLARE r RECORD;
  BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
      EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO pousada_app';
    END LOOP;
    FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
      EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequencename) || ' OWNER TO pousada_app';
    END LOOP;
  END \$\$;
  -- Garante privileges padrão para objetos futuros criados pelo postgres
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pousada_app;
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO pousada_app;
"

# 6. Roda as Migrations do Banco de Dados via Alembic
echo "🗄️ Executando migrações do banco de dados (Alembic)..."
docker compose exec backend alembic upgrade head

echo "✅ Deploy Finalizado! O sistema está no ar."
