"""forecast schedules and watchlist

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02 01:09:36.254884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('forecast_schedules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('horizon', sa.String(length=8), nullable=False),
    sa.Column('frequency', sa.String(length=8), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=True),
    sa.Column('hour', sa.Integer(), nullable=False),
    sa.Column('minute', sa.Integer(), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('lang', sa.String(length=4), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('next_run_at', sa.DateTime(), nullable=False),
    sa.Column('last_run_at', sa.DateTime(), nullable=True),
    sa.Column('last_status', sa.String(length=16), nullable=True),
    sa.Column('last_error', sa.String(length=255), nullable=True),
    sa.Column('last_forecast_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('forecast_schedules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_forecast_schedules_next_run_at'), ['next_run_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_forecast_schedules_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('watchlist_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('watchlist_json')

    with op.batch_alter_table('forecast_schedules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_forecast_schedules_user_id'))
        batch_op.drop_index(batch_op.f('ix_forecast_schedules_next_run_at'))

    op.drop_table('forecast_schedules')
