"""add_expenses_table

Revision ID: a1b2c3d4e5f6
Revises: 14a9921d050f
Create Date: 2026-04-15 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '14a9921d050f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cria o enum de forma idempotente (seguro contra re-execuções)
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE expensecategory AS ENUM (
                'agua', 'energia', 'internet', 'manutencao', 'fornecedor',
                'salarios', 'limpeza', 'alimentacao', 'marketing', 'impostos', 'outros'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    # Cria a tabela apenas se ainda não existir
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          SERIAL PRIMARY KEY,
            description VARCHAR NOT NULL,
            amount      FLOAT NOT NULL,
            category    expensecategory NOT NULL DEFAULT 'outros',
            due_date    DATE,
            paid_date   DATE,
            is_paid     BOOLEAN DEFAULT FALSE,
            payment_method paymentmethod,
            notes       TEXT,
            created_at  TIMESTAMP,
            created_by  VARCHAR,
            tenant_id   INTEGER REFERENCES tenants(id)
        );
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_expenses_id ON expenses (id);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_expenses_tenant_id ON expenses (tenant_id);"))


def downgrade() -> None:
    op.drop_index(op.f('ix_expenses_id'), table_name='expenses')
    op.drop_table('expenses')
    # O enum expensecategory é compartilhável — não remove para evitar problemas
