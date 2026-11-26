"""为团队主页保存独立的公开设置，已有团队保持关闭。"""

import sqlalchemy as sa
from alembic import op

revision = "4f7c1a032ce5"
down_revision = "0a20425c6fa2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("profile_public", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("teams", "profile_public")
