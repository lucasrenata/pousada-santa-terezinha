import os
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

# Conexão principal
db_url = os.getenv('DATABASE_ADMIN_URL') or os.getenv('DATABASE_URL')
if not db_url:
    # Fallback se .env não carregar
    db_url = 'postgresql://pousada_app:ParcerIA19141919%40@db:5432/pousada_db'

print(f"Conectando ao banco...")
engine = create_engine(db_url)

sql_file = 'create_product_categories.sql'
path = os.path.join('sql', sql_file)

with engine.connect() as conn:
    print(f"Executando {sql_file}...")
    with open(path, 'r') as f:
        sql = f.read()
        try:
            conn.execute(text(sql))
            conn.commit()
            print("🏁 Tabela criada com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao executar {sql_file}: {e}")
            conn.rollback()
