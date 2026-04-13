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
            # Adicionando colunas recém-criadas na branch main que não estavam na nuvem
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR"))
            
            conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_capacity INTEGER DEFAULT 2"))
            conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS maintenance_note TEXT"))
            
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS document VARCHAR"))
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS birth_date DATE"))
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS profession VARCHAR"))
            
            # Adicionando tenant_id nas tabelas legadas para a VPS
            tables = [
                "users", "rooms", "guests", "products", "bookings", 
                "companions", "consumptions", "revenues", "business_rules", 
                "chat_messages", "stock_entries", "stock_entry_items", 
                "settings", "events", "tenant_configs"
            ]
            for table in tables:
                if table == "tenant_configs":
                    # Cria a tabela tenant_configs manualmente se não existir (para evitar dependência de mixin)
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS tenant_configs (
                            id SERIAL PRIMARY KEY,
                            tenant_id INTEGER UNIQUE REFERENCES tenants(id),
                            mp_access_token VARCHAR,
                            mp_public_key VARCHAR,
                            is_active BOOLEAN DEFAULT TRUE,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)"))
            
            conn.commit()
            print("✅ Colunas de negócio e multitenancy (tenant_id) injetadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro na migração das tabelas (A tabela 'tenants' já foi gerada pelo FastAPI?): {e}")

if __name__ == "__main__":
    migrate()
