import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv(".env")
# No localhost, o Docker mapeia a porta 5432 do banco para a 5434 do seu computador
DATABASE_URL = "postgresql://admin:admin_password_123@localhost:5434/pousada_db"

def run_migration():
    print(f"Conectando ao banco em: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            print("Tentando adicionar coluna 'payment_receipt_url' à tabela 'bookings'...")
            # SQL para adicionar a coluna caso não exista
            conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_receipt_url VARCHAR;"))
            conn.commit()
            print("Sucesso! Coluna adicionada ou já existente.")
        except Exception as e:
            print(f"Erro na migração: {e}")

if __name__ == "__main__":
    run_migration()
