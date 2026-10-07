"""Status history and the weekly Beat the AI challenge

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-07 19:02:32.309040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('challenges',
    sa.Column('week', sa.String(length=10), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('start_price', sa.Float(), nullable=False),
    sa.Column('ai_price', sa.Float(), nullable=True),
    sa.Column('end_price', sa.Float(), nullable=True),
    sa.Column('winner_user_id', sa.Integer(), nullable=True),
    sa.Column('settled_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('week')
    )
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_challenges_winner_user_id'), ['winner_user_id'], unique=False)

    op.create_table('status_samples',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('checked_at', sa.DateTime(), nullable=False),
    sa.Column('service', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('status_samples', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_status_samples_checked_at'), ['checked_at'], unique=False)

    op.create_table('challenge_entries',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('week', sa.String(length=10), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('week_user', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('challenge_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_challenge_entries_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_challenge_entries_week'), ['week'], unique=False)
        batch_op.create_index(batch_op.f('ix_challenge_entries_week_user'), ['week_user'], unique=True)



def downgrade() -> None:
    with op.batch_alter_table('challenge_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_challenge_entries_week_user'))
        batch_op.drop_index(batch_op.f('ix_challenge_entries_week'))
        batch_op.drop_index(batch_op.f('ix_challenge_entries_user_id'))

    op.drop_table('challenge_entries')
    with op.batch_alter_table('status_samples', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_status_samples_checked_at'))

    op.drop_table('status_samples')
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_challenges_winner_user_id'))

    op.drop_table('challenges')
