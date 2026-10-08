"""Track record integrity and 2FA recovery codes

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-09 00:39:12.973838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('forecast_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('start_price', sa.Float(), nullable=True))

    with op.batch_alter_table('forecast_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signature', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('hidden_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_forecast_history_signature'), ['signature'], unique=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('totp_recovery_json', sa.Text(), nullable=True))



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('totp_recovery_json')

    with op.batch_alter_table('forecast_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_forecast_history_signature'))
        batch_op.drop_column('hidden_at')
        batch_op.drop_column('signature')

    with op.batch_alter_table('forecast_evaluations', schema=None) as batch_op:
        batch_op.drop_column('start_price')
        batch_op.drop_column('confidence')

