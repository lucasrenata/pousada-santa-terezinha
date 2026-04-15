from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import models

# Set up target metadata
target_metadata = models.Base.metadata

# Carrega variáveis de ambiente
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# ALEMBIC_DATABASE_URL → usado para migrations (usuário admin com privilégio DDL)
# DATABASE_URL         → usado pelo app em runtime (usuário pousada_app, só DML)
# Isso mantém a arquitetura de segurança: app não tem acesso DDL ao banco.
alembic_db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
if not alembic_db_url:
    raise RuntimeError(
        "Nenhuma DATABASE_URL ou ALEMBIC_DATABASE_URL definida. "
        "Configure o arquivo .env do backend."
    )
# Escape % para compatibilidade com configparser
alembic_db_url = alembic_db_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", alembic_db_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
