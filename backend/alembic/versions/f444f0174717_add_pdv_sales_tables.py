"""add pdv_sales tables

Revision ID: f444f0174717
Revises: 9692a3b498af
Create Date: 2026-04-18 19:33:39.436383

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f444f0174717'
down_revision: Union[str, Sequence[str], None] = '9692a3b498af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. pdv_sales
    op.create_table('pdv_sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('comanda_identificador', sa.String(), nullable=True),
        sa.Column('total_amount', sa.Float(), nullable=True),
        sa.Column('discount', sa.Float(), nullable=True),
        # Usamos o Enum existente 'paymentmethod' sem tentar criá-lo
        sa.Column('payment_method', postgresql.ENUM('PIX', 'CREDITO', 'DEBITO', 'DINHEIRO', name='paymentmethod', create_type=False), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['caixa_sessions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pdv_sales_comanda_identificador'), 'pdv_sales', ['comanda_identificador'], unique=False)
    op.create_index(op.f('ix_pdv_sales_id'), 'pdv_sales', ['id'], unique=False)
    op.create_index(op.f('ix_pdv_sales_tenant_id'), 'pdv_sales', ['tenant_id'], unique=False)

    # 2. pdv_sale_items
    op.create_table('pdv_sale_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('sale_id', sa.Integer(), nullable=True),
        sa.Column('product_name', sa.String(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('total_item', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['sale_id'], ['pdv_sales.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pdv_sale_items_id'), 'pdv_sale_items', ['id'], unique=False)
    op.create_index(op.f('ix_pdv_sale_items_tenant_id'), 'pdv_sale_items', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pdv_sale_items_tenant_id'), table_name='pdv_sale_items')
    op.drop_index(op.f('ix_pdv_sale_items_id'), table_name='pdv_sale_items')
    op.drop_table('pdv_sale_items')
    op.drop_index(op.f('ix_pdv_sales_tenant_id'), table_name='pdv_sales')
    op.drop_index(op.f('ix_pdv_sales_id'), table_name='pdv_sales')
    op.drop_index(op.f('ix_pdv_sales_comanda_identificador'), table_name='pdv_sales')
    op.drop_table('pdv_sales')
