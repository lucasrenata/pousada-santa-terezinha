from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin_password_123@localhost/pousada_db")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

Base = declarative_base()

# Gerenciador de contexto de Tenant na sessão SQL
def set_tenant_context(db: Session, tenant_id: int):
    """Define o ID do tenant para a sessão atual. -1 = Visão Global (SuperAdmin)"""
    # Armazena no .info da sessão para fácil recuperação no Python (before_flush) sem precisar de SQL
    db.info['tenant_id'] = tenant_id

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
        # Reset de segurança e configuração de fuso horário
        db.info['tenant_id'] = 0
        db.execute(text("SET app.current_tenant = '0'"))
        db.execute(text("SET timezone TO 'America/Sao_Paulo'"))
        yield db
    finally:
        db.close()

# Evento para garantir que toda transação iniciada sincronize o contexto RLS no banco
@event.listens_for(Session, "after_begin")
def after_begin(session, transaction, connection):
    """
    SINCRONIZAÇÃO DEFINITIVA DE RLS:
    A raiz do problema em sistemas multi-tenant com pool de conexões é que o 'SET app.current_tenant'
    é volátil e se perde se a conexão for devolvida ao pool ou se a sessão abrir uma nova transação.
    Este 'hook' garante que SEMPRE que uma transação começar no SQLAlchemy, o banco de dados
    receberá a identidade correta da pousada antes de qualquer comando SQL.
    """
    tid = session.info.get('tenant_id')
    if tid is not None:
        # Força o ID do tenant na conexão atual da transação
        connection.execute(text("SET app.current_tenant = :tid"), {"tid": str(tid)})

# Evento para garantir que todo objeto novo herde o tenant_id da sessão (Segurança de Dados)
@event.listens_for(Session, "before_flush")
def before_flush(session, flush_context, instances):
    """
    Este evento garante a integridade dos dados no nível da aplicação.
    Ele preenche o campo 'tenant_id' nos objetos Python antes de enviar ao banco,
    evitando erros de 'NOT NULL constraint' e servindo como segunda camada ao RLS.
    """
    try:
        current_tid = session.info.get('tenant_id')
        
        if current_tid and isinstance(current_tid, int) and current_tid > 0:
            # Verifica novos objetos E objetos modificados (dirty)
            for obj in list(session.new) + list(session.dirty):
                if hasattr(obj, 'tenant_id') and getattr(obj, 'tenant_id') is None:
                    setattr(obj, 'tenant_id', current_tid)
    except Exception as e:
        # Log de erro silencioso para não quebrar a transação se o auto-preenchimento falhar
        # (O RLS no banco ainda servirá como barreira final)
        print(f"Erro ao auto-atribuir tenant_id: {e}")
