import os
from sqlalchemy import create_engine, text

def migrate():
    # Usa a URL de admin para migrações
    db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine_admin = create_engine(db_url)
    
    with engine_admin.connect() as conn:
        print(f"Iniciando migração do banco com usuário: {db_url.split('://')[1].split(':')[0]}")
        try:
            # 1. Colunas de Horários e Preços base
            conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS check_in_time VARCHAR DEFAULT '14:00'"))
            conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS check_out_time VARCHAR DEFAULT '14:00'"))
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS cost_price FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS markup_percent FLOAT DEFAULT 0.0"))
            
            # 2. Usuários e Quartos
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR"))
            conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_capacity INTEGER DEFAULT 2"))
            conn.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS maintenance_note TEXT"))
            
            # 3. Hóspedes
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS document VARCHAR"))
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS birth_date DATE"))
            conn.execute(text("ALTER TABLE guests ADD COLUMN IF NOT EXISTS profession VARCHAR"))
            
            # 4. NOVAS COLUNAS: Eventos e Configurações (Preços inteligentes)
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS daily_rate FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS daily_rate_single FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS daily_rate_couple FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS daily_rate_extra FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS daily_rate_child FLOAT DEFAULT 0.0"))
            
            conn.execute(text("ALTER TABLE tenant_configs ADD COLUMN IF NOT EXISTS manual_pix_key VARCHAR"))

            # 5. PDV e Comandas
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS caixa_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    opening_balance FLOAT DEFAULT 0.0,
                    closing_balance FLOAT,
                    status VARCHAR DEFAULT 'aberto',
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    tenant_id INTEGER REFERENCES tenants(id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS caixa_movements (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES caixa_sessions(id),
                    type VARCHAR,
                    amount FLOAT,
                    description VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id INTEGER REFERENCES tenants(id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS comandas (
                    id SERIAL PRIMARY KEY,
                    identificador VARCHAR,
                    status VARCHAR DEFAULT 'aberta',
                    total FLOAT DEFAULT 0.0,
                    booking_id INTEGER REFERENCES bookings(id),
                    session_id INTEGER REFERENCES caixa_sessions(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id INTEGER REFERENCES tenants(id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS comanda_items (
                    id SERIAL PRIMARY KEY,
                    comanda_id INTEGER REFERENCES comandas(id),
                    product_id INTEGER REFERENCES products(id),
                    quantity FLOAT DEFAULT 1.0,
                    unit_price FLOAT,
                    description VARCHAR,
                    type VARCHAR DEFAULT 'produto',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tenant_id INTEGER REFERENCES tenants(id)
                )
            """))

            # 6. Multi-tenancy (tenant_id em todas as tabelas)
            tables = [
                "users", "rooms", "guests", "products", "bookings", 
                "companions", "consumptions", "revenues", "business_rules", 
                "chat_messages", "stock_entries", "stock_entry_items", 
                "settings", "events", "tenant_configs",
                "caixa_sessions", "caixa_movements", "comandas", "comanda_items"
            ]
            for table in tables:
                if table == "tenant_configs":
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
            print("✅ Banco de dados sincronizado com sucesso!")
        except Exception as e:
            print(f"❌ Erro na migração: {e}")

if __name__ == "__main__":
    migrate()
