"""Master Sync: Add missing tables and columns

Revision ID: e4a5b6c7d8e9
Revises: 30c4f3ff5300
Create Date: 2026-05-03 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = '30c4f3ff5300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Criar tabela product_categories
    op.execute('''
        CREATE TABLE IF NOT EXISTS product_categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    op.execute('CREATE INDEX IF NOT EXISTS ix_product_categories_id ON product_categories (id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_product_categories_name ON product_categories (name)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_product_categories_tenant_id ON product_categories (tenant_id)')

    # 2. Sincronizar colunas faltantes em products
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS cost_price FLOAT DEFAULT 0.0')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS markup_percent FLOAT DEFAULT 0.0')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS is_quick_access BOOLEAN DEFAULT FALSE')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS supplier VARCHAR')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS unit_measure VARCHAR DEFAULT \'UN\'')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS min_stock INTEGER DEFAULT 5')
    op.execute('ALTER TABLE products ADD COLUMN IF NOT EXISTS max_stock INTEGER')

    # 3. Sincronizar colunas faltantes em rooms
    op.execute('ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_capacity INTEGER DEFAULT 2')
    op.execute('ALTER TABLE rooms ADD COLUMN IF NOT EXISTS maintenance_note TEXT')

    # 4. Sincronizar colunas em bookings (Garantia)
    op.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now()')
    op.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now()')
    op.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_receipt_url VARCHAR')

    # 5. Criar índices de Tenant para as novas tabelas
    op.execute('CREATE INDEX IF NOT EXISTS ix_product_categories_tenant_id ON product_categories (tenant_id)')

def downgrade() -> None:
    op.drop_table('product_categories')
    # Nota: Downgrade de colunas individuais pode ser arriscado se houver dados, 
    # mas mantemos o padrão se necessário.
