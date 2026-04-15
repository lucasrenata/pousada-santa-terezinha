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

# 5. Re-provisiona permissões do banco (necessário após recriação de tabelas)
# Garante que pousada_app seja dono de TODAS as tabelas e sequences existentes.
# Isso evita erros "InsufficientPrivilege" no Alembic.
echo "🔑 Provisionando permissões do banco de dados..."
docker compose exec -T db psql -U postgres -d pousada_db -c "
  DO \$\$
  DECLARE
    r RECORD;
  BEGIN
    -- Transfere ownership de todas as tabelas para pousada_app
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
      EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO pousada_app';
    END LOOP;
    -- Transfere ownership de todas as sequences para pousada_app
    FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
      EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequencename) || ' OWNER TO pousada_app';
    END LOOP;
  END \$\$;
  -- Garante privileges padrão para tabelas futuras criadas pelo postgres
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pousada_app;
  ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO pousada_app;
"

# 6. Roda as Migrations do Banco de Dados via Alembic
echo "🗄️ Executando migrações do banco de dados (Alembic)..."
docker compose exec backend alembic upgrade head

echo "✅ Deploy Finalizado! O sistema está no ar."
