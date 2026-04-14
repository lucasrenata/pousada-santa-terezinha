from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin_password_123@localhost/pousada_db")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Gerenciador de contexto de Tenant na sessão SQL
def set_tenant_context(db: Session, tenant_id: int):
    """Define o ID do tenant para a sessão atual. -1 = Visão Global (SuperAdmin)"""
    if tenant_id == -1:
        # Define um valor que o banco/RLS entende como 'ver tudo'
        db.execute(text("SET app.current_tenant = '-1'"))
    elif tenant_id is not None:
        db.execute(text("SET app.current_tenant = :tid"), {"tid": str(tenant_id)})
    else:
        db.execute(text("SET app.current_tenant = '0'"))

# Dependência para pegar a sessão do banco em cada requisição
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Evento para garantir que todo objeto novo herde o tenant_id da sessão (opcional, mas seguro)
@event.listens_for(Session, "before_flush")
def before_flush(session, flush_context, instances):
    # Tenta pegar o tenant_id da configuração da sessão
    try:
        # Usa current_setting com 'true' para não dar erro se o parâmetro não existir
        res = session.execute(text("SELECT current_setting('app.current_tenant', true)")).fetchone()
        current_tid = int(res[0]) if res and res[0] and res[0].isdigit() and res[0] != '0' else None
        
        if current_tid:
            for obj in session.new:
                if hasattr(obj, 'tenant_id') and obj.tenant_id is None:
                    obj.tenant_id = current_tid
    except Exception as e:
        print(f"Erro ao auto-atribuir tenant_id: {e}")
