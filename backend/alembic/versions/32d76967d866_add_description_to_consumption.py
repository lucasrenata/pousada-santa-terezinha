"""add_description_to_consumption

Revision ID: 32d76967d866
Revises: f444f0174717
Create Date: 2026-04-19 00:20:27.463110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32d76967d866'
down_revision: Union[str, Sequence[str], None] = 'f444f0174717'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Verifica se a coluna já existe antes de tentar adicionar
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('consumptions')]
    
    if 'description' not in columns:
        op.add_column('consumptions', sa.Column('description', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('consumptions', 'description')
