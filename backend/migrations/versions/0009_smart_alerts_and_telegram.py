"""smart alerts and telegram

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-07 13:42:07.064567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind', sa.String(length=16), server_default='price', nullable=False))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telegram_chat_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('telegram_link_code', sa.String(length=16), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_telegram_link_code'), ['telegram_link_code'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_telegram_link_code'))
        batch_op.drop_column('telegram_link_code')
        batch_op.drop_column('telegram_chat_id')

    with op.batch_alter_table('price_alerts', schema=None) as batch_op:
        batch_op.drop_column('kind')

