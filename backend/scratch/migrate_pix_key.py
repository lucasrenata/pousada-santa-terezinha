import os
import sqlite3
import psycopg2
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pousada_db")

def migrate():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        try:
            print("Tentando adicionar coluna manual_pix_key à tabela tenant_configs...")
            conn.execute(text("ALTER TABLE tenant_configs ADD COLUMN manual_pix_key VARCHAR;"))
            conn.commit()
            print("Coluna adicionada com sucesso!")
        except Exception as e:
            if "already exists" in str(e):
                print("A coluna já existe. Pulando...")
            else:
                print(f"Erro ao migrar: {e}")

if __name__ == "__main__":
    migrate()
