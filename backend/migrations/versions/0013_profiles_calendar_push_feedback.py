"""Profiles, calendar reminders, push, feedback, simple mode

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-08 11:10:21.873121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, Sequence[str], None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('coin_signal_states',
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('direction', sa.String(length=8), nullable=False),
    sa.Column('last_trend', sa.String(length=8), nullable=True),
    sa.Column('change_pct', sa.Float(), nullable=True),
    sa.Column('flipped_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('coin')
    )
    op.create_table('event_reminders',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.String(length=64), nullable=False),
    sa.Column('event_at', sa.DateTime(), nullable=False),
    sa.Column('title_key', sa.String(length=32), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'event_id', name='uq_event_reminder_user_event')
    )
    with op.batch_alter_table('event_reminders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_reminders_event_at'), ['event_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_reminders_user_id'), ['user_id'], unique=False)

    op.create_table('feedback',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('page', sa.String(length=200), nullable=True),
    sa.Column('lang', sa.String(length=4), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_feedback_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_feedback_user_id'), ['user_id'], unique=False)

    op.create_table('push_subscriptions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('endpoint', sa.String(length=1024), nullable=False),
    sa.Column('p256dh', sa.String(length=255), nullable=False),
    sa.Column('auth', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_ok_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    with op.batch_alter_table('push_subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_subscriptions_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('simple_mode', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('notify_prefs_json', sa.Text(), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('notify_prefs_json')
        batch_op.drop_column('simple_mode')

    with op.batch_alter_table('push_subscriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_subscriptions_user_id'))

    op.drop_table('push_subscriptions')
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_feedback_user_id'))
        batch_op.drop_index(batch_op.f('ix_feedback_created_at'))

    op.drop_table('feedback')
    with op.batch_alter_table('event_reminders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_event_reminders_user_id'))
        batch_op.drop_index(batch_op.f('ix_event_reminders_event_at'))

    op.drop_table('event_reminders')
    op.drop_table('coin_signal_states')
