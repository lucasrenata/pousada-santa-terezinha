"""create portal tables surgical

Revision ID: 4300393037aa
Revises: 31d81c31a57b
Create Date: 2026-03-05 17:19:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4300393037aa'
down_revision = '31d81c31a57b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Manual creation of portal_slides table based on app/models/portal.py
    op.create_table(
        'portal_slides',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('position', sa.String(length=50), nullable=False), # 'left' ou 'right'
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Manual creation of portal_videos table based on app/models/portal.py
    op.create_table(
        'portal_videos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('video_url', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('portal_videos')
    op.drop_table('portal_slides')
