from database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("Iniciando migração do banco de dados...")
        try:
            # Adiciona colunas de horário se não existirem
            conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS check_in_time VARCHAR DEFAULT '14:00'"))
            conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS check_out_time VARCHAR DEFAULT '14:00'"))
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS cost_price FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS markup_percent FLOAT DEFAULT 0.0"))
            conn.commit()
            print("✅ Colunas de horário adicionadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao adicionar colunas: {e}")

if __name__ == "__main__":
    migrate()
