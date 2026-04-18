"""add pdv tables

Revision ID: 9692a3b498af
Revises: 6c72c31b9128
Create Date: 2026-04-18 18:47:55.152300

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9692a3b498af'
down_revision: Union[str, Sequence[str], None] = '6c72c31b9128'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Comandos para Criar Tabelas PDV ###
    
    # 1. CaixaSession
    op.create_table('caixa_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('opening_balance', sa.Float(), nullable=True),
        sa.Column('closing_balance', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('ABERTO', 'FECHADO', name='caixastatus'), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('summary_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_caixa_sessions_id'), 'caixa_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_caixa_sessions_tenant_id'), 'caixa_sessions', ['tenant_id'], unique=False)

    # 2. CaixaMovement
    op.create_table('caixa_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.Enum('SUPRIMENTO', 'SANGRIA', 'VENDA', 'RETIRADA', name='caixamovementtype'), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('payment_method', sa.Enum('PIX', 'CREDITO', 'DEBITO', 'DINHEIRO', name='paymentmethod', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['caixa_sessions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_caixa_movements_id'), 'caixa_movements', ['id'], unique=False)
    op.create_index(op.f('ix_caixa_movements_tenant_id'), 'caixa_movements', ['tenant_id'], unique=False)

    # 3. Comanda
    op.create_table('comandas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('identificador', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('ABERTA', 'PAGA', 'CANCELADA', 'LANCADA_NO_QUARTO', name='comandastatus'), nullable=True),
        sa.Column('total', sa.Float(), nullable=True),
        sa.Column('booking_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['caixa_sessions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comandas_id'), 'comandas', ['id'], unique=False)
    op.create_index(op.f('ix_comandas_identificador'), 'comandas', ['identificador'], unique=False)
    op.create_index(op.f('ix_comandas_tenant_id'), 'comandas', ['tenant_id'], unique=False)

    # 4. ComandaItem
    op.create_table('comanda_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('comanda_id', sa.Integer(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('type', sa.Enum('PRODUTO', 'PESO', 'MARMITEX', name='comandaitemtype'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comanda_id'], ['comandas.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comanda_items_id'), 'comanda_items', ['id'], unique=False)
    op.create_index(op.f('ix_comanda_items_tenant_id'), 'comanda_items', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_comanda_items_tenant_id'), table_name='comanda_items')
    op.drop_index(op.f('ix_comanda_items_id'), table_name='comanda_items')
    op.drop_table('comanda_items')
    
    op.drop_index(op.f('ix_comandas_tenant_id'), table_name='comandas')
    op.drop_index(op.f('ix_comandas_identificador'), table_name='comandas')
    op.drop_index(op.f('ix_comandas_id'), table_name='comandas')
    op.drop_table('comandas')
    
    op.drop_index(op.f('ix_caixa_movements_tenant_id'), table_name='caixa_movements')
    op.drop_index(op.f('ix_caixa_movements_id'), table_name='caixa_movements')
    op.drop_table('caixa_movements')
    
    op.drop_index(op.f('ix_caixa_sessions_tenant_id'), table_name='caixa_sessions')
    op.drop_index(op.f('ix_caixa_sessions_id'), table_name='caixa_sessions')
    op.drop_table('caixa_sessions')
    
    # Drop Enums (Postgres specific)
    op.execute("DROP TYPE caixastatus")
    op.execute("DROP TYPE caixamovementtype")
    op.execute("DROP TYPE comandastatus")
    op.execute("DROP TYPE comandaitemtype")
