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

# 5. Roda as Migrations do Banco de Dados via Alembic
# O Alembic usa ALEMBIC_DATABASE_URL do .env (usuário admin com DDL completo).
# O app em si usa DATABASE_URL do docker-compose (usuário pousada_app, só DML).
# Isso garante a separação de privilégios e a segurança da arquitetura multi-tenant.
echo "🗄️ Executando migrações do banco de dados (Alembic)..."
docker compose exec backend alembic upgrade head

echo "✅ Deploy Finalizado! O sistema está no ar."
