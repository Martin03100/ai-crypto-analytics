"""community and premium

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07 11:22:14.418127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('job_runs',
    sa.Column('name', sa.String(length=48), nullable=False),
    sa.Column('last_run_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('data_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nickname', sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column('digest_opt_in', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('lang', sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column('premium_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('referral_code', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('referred_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('referral_rewarded', sa.Boolean(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_nickname'), ['nickname'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_referral_code'), ['referral_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_stripe_customer_id'), ['stripe_customer_id'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_stripe_customer_id'))
        batch_op.drop_index(batch_op.f('ix_users_referral_code'))
        batch_op.drop_index(batch_op.f('ix_users_nickname'))
        batch_op.drop_column('referral_rewarded')
        batch_op.drop_column('referred_by_id')
        batch_op.drop_column('referral_code')
        batch_op.drop_column('stripe_customer_id')
        batch_op.drop_column('premium_until')
        batch_op.drop_column('lang')
        batch_op.drop_column('digest_opt_in')
        batch_op.drop_column('nickname')

    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))
        batch_op.drop_index(batch_op.f('ix_notifications_created_at'))

    op.drop_table('notifications')
    op.drop_table('job_runs')
