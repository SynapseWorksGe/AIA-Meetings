"""Add yandex_api_key and yandex_folder_id to user_settings.

Revision ID: 003_yandex_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "003_yandex_fields"
down_revision = "002_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("yandex_api_key", sa.String(500), nullable=True))
    op.add_column("user_settings", sa.Column("yandex_folder_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "yandex_folder_id")
    op.drop_column("user_settings", "yandex_api_key")
