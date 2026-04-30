import asyncio
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

async def setup_checkpointer():
    conn_string = os.getenv("DATABASE_URL") or os.getenv("ALEMBIC_DATABASE_URL")
    if not conn_string:
        conn_string = "postgresql://pousada_app:ParcerIA19141919@db:5432/pousada_db"
    
    print(f"Iniciando setup do checkpointer em: {conn_string}")
    async with AsyncConnectionPool(conn_string) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        print("✅ Tabelas de checkpoint criadas com sucesso!")

if __name__ == "__main__":
    asyncio.run(setup_checkpointer())
