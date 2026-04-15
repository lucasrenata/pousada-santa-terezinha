"""fix_settings_uniqueness

Revision ID: 14a9921d050f
Revises: 081fc61903f8
Create Date: 2026-04-14 19:26:13.760722

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '14a9921d050f'
down_revision: Union[str, Sequence[str], None] = '081fc61903f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Cria índice e constraint de unicidade na tabela settings.
    Usa SQL bruto com IF NOT EXISTS / DO EXCEPTION para ser idempotente
    e funcionar mesmo quando pousada_app não é owner da tabela (VPS legada).
    """
    # Cria o índice apenas se não existir
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_settings_key ON settings (key);"
    ))

    # Adiciona a constraint de unicidade composta apenas se ainda não existir
    op.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE settings
                ADD CONSTRAINT uq_settings_key_tenant UNIQUE (key, tenant_id);
        EXCEPTION WHEN duplicate_table THEN
            NULL;  -- constraint já existe, ignora
        END $$;
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE settings DROP CONSTRAINT IF EXISTS uq_settings_key_tenant;"
    ))
    op.execute(sa.text(
        "DROP INDEX IF EXISTS ix_settings_key;"
    ))
