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

# 4. Aguarda o Postgres e o Backend inicializarem (10s costuma ser o suficiente)
echo "⏳ Aguardando os serviços iniciarem para rodar as migrações..."
sleep 10

# 5. Roda as Migrations do Banco de Dados via Alembic
echo "🗄️ Executando migrações do banco de dados (Alembic)..."
docker compose exec backend alembic upgrade head

echo "✅ Deploy Finalizado! O sistema está no ar."
