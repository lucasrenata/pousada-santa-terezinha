from sqlalchemy import create_engine, text
import os

db_url = "postgresql://admin:admin_password_123@localhost:5434/pousada_db"
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Verificando colunas...")
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='caixa_movements'"))
    columns = [r[0] for r in res]
    print(f"Colunas atuais: {columns}")
    
    if 'payment_method' not in columns:
        print("Adicionando coluna payment_method...")
        conn.execute(text("ALTER TABLE caixa_movements ADD COLUMN payment_method VARCHAR(50)"))
        conn.commit()
        print("Coluna adicionada com sucesso!")
    else:
        print("Coluna payment_method já existe.")
