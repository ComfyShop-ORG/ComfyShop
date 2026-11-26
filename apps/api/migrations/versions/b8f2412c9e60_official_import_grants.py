"""为账号保存官方服务清单导入授权。"""

import sqlalchemy as sa
from alembic import op

revision = "b8f2412c9e60"
down_revision = "d522fa8dee69"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "official_import_granted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "official_import_granted")
