"""forecast evaluation tracking

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01 23:55:17.049127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("forecast_history", schema=None) as batch_op:
        batch_op.add_column(sa.Column("eval_attempts", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("eval_last_try_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_forecast_history_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("forecast_history", schema=None) as batch_op:
        batch_op.drop_index("ix_forecast_history_user_id")
        batch_op.drop_column("eval_last_try_at")
        batch_op.drop_column("eval_attempts")
