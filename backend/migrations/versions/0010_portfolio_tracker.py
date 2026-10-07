"""portfolio tracker

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 13:45:02.386327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('portfolio_positions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('avg_buy_price', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'coin', name='uq_position_user_coin')
    )
    with op.batch_alter_table('portfolio_positions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_positions_user_id'), ['user_id'], unique=False)

    op.create_table('portfolio_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('day', sa.String(length=10), nullable=False),
    sa.Column('value_usd', sa.Float(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'day', name='uq_snapshot_user_day')
    )
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_snapshots_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('portfolio_snapshots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_snapshots_user_id'))

    op.drop_table('portfolio_snapshots')
    with op.batch_alter_table('portfolio_positions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_positions_user_id'))

    op.drop_table('portfolio_positions')
