"""Stripe webhook events already handled

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-07 17:54:41.424872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('stripe_events',
    sa.Column('id', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('stripe_events')
