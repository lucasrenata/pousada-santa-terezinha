import asyncio
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

async def setup_checkpointer():
    # Usa o usuário admin para ter permissão de criar tabelas
    conn_string = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not conn_string:
        raise ValueError("DATABASE_URL não configurada no .env")
    
    print(f"Iniciando setup do checkpointer em: {conn_string.split('://')[1].split(':')[0]}")
    # O setup do LangGraph exige o método correto de conexão da versão 3.0.x
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        print("✅ Tabelas de checkpoint criadas com sucesso!")

if __name__ == "__main__":
    asyncio.run(setup_checkpointer())
