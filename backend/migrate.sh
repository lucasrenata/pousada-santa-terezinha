#!/bin/bash
# Script de Migração Automática para VPS
echo "--------------------------------------------------"
echo "🚀 [POUSADA SYSTEM] Iniciando migrações do banco..."
echo "--------------------------------------------------"

# Executa as migrações do Alembic dentro do container
docker exec pousada_backend alembic upgrade head

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------"
    echo "✅ [SUCCESS] Banco de dados atualizado com sucesso!"
    echo "--------------------------------------------------"
else
    echo "--------------------------------------------------"
    echo "❌ [ERROR] Falha ao executar migrações!"
    echo "--------------------------------------------------"
    exit 1
fi
