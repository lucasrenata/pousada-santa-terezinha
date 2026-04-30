"""add_cnpj_address_to_tenant

Revision ID: 30c4f3ff5300
Revises: 66656b09bb1a
Create Date: 2026-04-29 23:03:57.994841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30c4f3ff5300'
down_revision: Union[str, Sequence[str], None] = '66656b09bb1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('ALTER TABLE tenants ADD COLUMN IF NOT EXISTS cnpj VARCHAR')
    op.execute('ALTER TABLE tenants ADD COLUMN IF NOT EXISTS address VARCHAR')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tenants', 'address')
    op.drop_column('tenants', 'cnpj')
