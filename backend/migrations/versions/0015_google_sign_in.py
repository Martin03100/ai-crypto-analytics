"""Sign in with Google

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-14 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, Sequence[str], None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_sub', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('password_set', sa.Boolean(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_google_sub'), ['google_sub'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_google_sub'))
        batch_op.drop_column('password_set')
        batch_op.drop_column('google_sub')
