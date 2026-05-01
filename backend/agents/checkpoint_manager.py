import os
import asyncio
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

class CheckpointManager:
    _instance = None
    _pool = None
    _saver = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            # Prioriza a URL de Admin para o checkpointer, pois ele precisa criar/gerir tabelas próprias
            db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL_ASYNCPG") or os.getenv("DATABASE_URL")
            
            # Converte para formato psycopg se necessário
            if db_url and db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql://", 1)
            
            # Garante que usamos o host 'db' se estiver no docker
            if "localhost" in db_url and os.getenv("DOCKER_ENV"):
                db_url = db_url.replace("localhost", "db")

            try:
                cls._pool = AsyncConnectionPool(conninfo=db_url, max_size=10, kwargs={"autocommit": True})
                cls._saver = AsyncPostgresSaver(cls._pool)
                
                # Inicializa as tabelas se necessário
                await cls._saver.setup()
                cls._instance = cls._saver
            except Exception as e:
                import logging
                logger = logging.getLogger("CheckpointManager")
                logger.error(f"Erro ao inicializar CheckpointManager: {e}")
                if "permission denied" in str(e).lower():
                    logger.error("DICA: Execute 'GRANT ALL ON SCHEMA public TO pousada_app;' no banco de dados.")
                raise e
            
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            cls._instance = None
