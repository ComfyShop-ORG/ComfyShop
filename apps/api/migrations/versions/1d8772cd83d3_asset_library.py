"""保存个人资产库中的素材。"""

import sqlalchemy as sa
from alembic import op

revision = "1d8772cd83d3"
down_revision = "b8f2412c9e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("saved_at", sa.BigInteger(), nullable=True))
    op.create_index("ix_assets_owner_saved", "assets", ["owner_id", "saved_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_assets_owner_saved", table_name="assets")
    op.drop_column("assets", "saved_at")
