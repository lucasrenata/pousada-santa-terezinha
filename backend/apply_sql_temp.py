import os
from sqlalchemy import text, create_engine

# Conexão de ADMIN
admin_url = 'postgresql://admin:admin_password_123@db:5432/pousada_db'
engine = create_engine(admin_url)

sql_files = ['provision_db_user.sql', 'init_rls.sql']

with engine.connect() as conn:
    # Bypassa RLS
    conn.execute(text("SET app.current_tenant = '-1'"))
    
    for filename in sql_files:
        path = os.path.join('sql', filename)
        print(f"Executando {filename}...")
        with open(path, 'r') as f:
            sql = f.read()
            try:
                # O SQLAlchemy 2.0+ exige commit explícito ou usar engine.begin()
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"Erro ao executar {filename}: {e}")
                conn.rollback()

print("🏁 SQL aplicado com sucesso!")
