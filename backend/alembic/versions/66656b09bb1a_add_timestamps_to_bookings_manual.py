"""add_timestamps_to_bookings_manual

Revision ID: 66656b09bb1a
Revises: 7e45b3a6b979
Create Date: 2026-04-29 21:19:38.024026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66656b09bb1a'
down_revision: Union[str, Sequence[str], None] = '7e45b3a6b979'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Adiciona colunas de timestamp na tabela de reservas
    op.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now()')
    op.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now()')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bookings', 'updated_at')
    op.drop_column('bookings', 'created_at')
