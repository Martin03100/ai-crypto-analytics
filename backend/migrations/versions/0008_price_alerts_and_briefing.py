"""price alerts and briefing

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-07 12:39:48.865348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('price_alerts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('direction', sa.String(length=8), nullable=False),
    sa.Column('target_price', sa.Float(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('triggered_at', sa.DateTime(), nullable=True),
    sa.Column('triggered_price', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_price_alerts_active'), ['active'], unique=False)
        batch_op.create_index(batch_op.f('ix_price_alerts_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('briefing_opt_in', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('briefing_opt_in')

    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_price_alerts_user_id'))
        batch_op.drop_index(batch_op.f('ix_price_alerts_active'))

    op.drop_table('price_alerts')
