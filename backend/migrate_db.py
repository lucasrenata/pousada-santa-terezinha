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
            # Adicionando tenant_id nas tabelas legadas para a VPS
            tables = [
                "users", "rooms", "guests", "products", "bookings", 
                "companions", "consumptions", "revenues", "business_rules", 
                "chat_messages", "stock_entries", "stock_entry_items", 
                "settings", "events"
            ]
            for table in tables:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)"))
            
            conn.commit()
            print("✅ Colunas de negócio e multitenancy (tenant_id) injetadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro na migração das tabelas (A tabela 'tenants' já foi gerada pelo FastAPI?): {e}")

if __name__ == "__main__":
    migrate()
