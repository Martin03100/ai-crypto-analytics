"""baseline schema

The schema as it was when Alembic was introduced (previously created by create_all + auto_migrate).

Revision ID: 0001
Revises:
Create Date: 2026-10-01 23:55:00.326502

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('forecast_evaluations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('forecast_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('coin', sa.String(length=16), nullable=False),
    sa.Column('timeframe', sa.String(length=8), nullable=False),
    sa.Column('accuracy_pct', sa.Float(), nullable=False),
    sa.Column('baseline_accuracy_pct', sa.Float(), nullable=True),
    sa.Column('direction_correct', sa.Boolean(), nullable=False),
    sa.Column('actual_final_price', sa.Float(), nullable=False),
    sa.Column('evaluated_at', sa.DateTime(), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('forecast_evaluations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_forecast_evaluations_forecast_id'), ['forecast_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_forecast_evaluations_provider'), ['provider'], unique=False)
        batch_op.create_index(batch_op.f('ix_forecast_evaluations_user_id'), ['user_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('token_version', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.Column('email_verified', sa.Boolean(), nullable=True),
    sa.Column('totp_secret', sa.Text(), nullable=True),
    sa.Column('totp_pending_secret', sa.Text(), nullable=True),
    sa.Column('totp_enabled', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('details', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_user_id'), ['user_id'], unique=False)

    op.create_table('community_votes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sentiment_vote', sa.String(length=16), nullable=False),
    sa.Column('voted_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('community_votes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_community_votes_voted_at'), ['voted_at'], unique=False)

    op.create_table('email_verification_codes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('email_verification_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_verification_codes_user_id'), ['user_id'], unique=False)

    op.create_table('forecast_history',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('crypto_symbol', sa.String(length=16), nullable=False),
    sa.Column('timeframe', sa.String(length=8), nullable=False),
    sa.Column('model_used', sa.String(length=32), nullable=False),
    sa.Column('forecast_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('share_token', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('forecast_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_forecast_history_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_forecast_history_share_token'), ['share_token'], unique=False)

    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_reset_tokens_token_hash'), ['token_hash'], unique=False)

    op.create_table('portfolio_history',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('holdings_json', sa.Text(), nullable=False),
    sa.Column('analysis_json', sa.Text(), nullable=False),
    sa.Column('model_used', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('portfolio_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_history_created_at'), ['created_at'], unique=False)

    op.create_table('price_tips',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('forecast_id', sa.Integer(), nullable=False),
    sa.Column('tip_price', sa.Float(), nullable=False),
    sa.Column('ai_price', sa.Float(), nullable=False),
    sa.Column('outcome', sa.String(length=8), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('price_tips', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_price_tips_forecast_id'), ['forecast_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_price_tips_user_id'), ['user_id'], unique=False)

    op.create_table('user_api_keys',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('encrypted_key', sa.Text(), nullable=False),
    sa.Column('key_suffix', sa.String(length=8), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'provider', name='uq_user_provider')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('user_api_keys')
    with op.batch_alter_table('price_tips', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_price_tips_user_id'))
        batch_op.drop_index(batch_op.f('ix_price_tips_forecast_id'))

    op.drop_table('price_tips')
    with op.batch_alter_table('portfolio_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_history_created_at'))

    op.drop_table('portfolio_history')
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_password_reset_tokens_token_hash'))

    op.drop_table('password_reset_tokens')
    with op.batch_alter_table('forecast_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_forecast_history_share_token'))
        batch_op.drop_index(batch_op.f('ix_forecast_history_created_at'))

    op.drop_table('forecast_history')
    with op.batch_alter_table('email_verification_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_verification_codes_user_id'))

    op.drop_table('email_verification_codes')
    with op.batch_alter_table('community_votes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_community_votes_voted_at'))

    op.drop_table('community_votes')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_created_at'))

    op.drop_table('audit_events')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))

    op.drop_table('users')
    with op.batch_alter_table('forecast_evaluations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_forecast_evaluations_user_id'))
        batch_op.drop_index(batch_op.f('ix_forecast_evaluations_provider'))
        batch_op.drop_index(batch_op.f('ix_forecast_evaluations_forecast_id'))

    op.drop_table('forecast_evaluations')
