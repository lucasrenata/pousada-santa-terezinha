from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
# Forçamos a URL do local se estivermos no host
db_url = "postgresql://admin:admin_password_123@localhost:5434/pousada_db"
engine = create_engine(db_url)

with engine.connect() as conn:
    # Verifica colunas da tabela bookings
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'bookings'"))
    columns = [r[0] for r in res.fetchall()]
    print(f"Colunas encontradas em 'bookings': {columns}")
    
    # Verifica se a tabela alembic_version existe
    res = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"))
    print(f"Tabela alembic_version existe: {res.fetchone()[0]}")
