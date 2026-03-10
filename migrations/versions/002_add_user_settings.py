"""Add user_settings table.

Revision ID: 002_user_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "002_user_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("selected_model", sa.String(50), server_default="claude-sonnet-4", nullable=False),
        sa.Column("anthropic_api_key", sa.String(500), nullable=True),
        sa.Column("openai_api_key", sa.String(500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
