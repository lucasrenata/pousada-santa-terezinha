import os
from redis import Redis
from rq import Worker, Queue, Connection
import logging

# Configuração de Logging para o Worker
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AI_WORKER")

listen = ['default']
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

try:
    conn = Redis.from_url(redis_url)
    logger.info(f"Conectado ao Redis em: {redis_url}")
except Exception as e:
    logger.error(f"Erro ao conectar ao Redis: {e}")
    exit(1)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        logger.info("Worker de IA iniciado e aguardando tarefas...")
        worker.work()
