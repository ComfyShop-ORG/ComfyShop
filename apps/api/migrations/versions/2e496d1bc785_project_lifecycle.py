"""保存项目归档和软删除状态。"""

import sqlalchemy as sa
from alembic import op

revision = "2e496d1bc785"
down_revision = "91f608b5c1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("archived_at", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("deleted_at", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(
        sa.text(
            "SELECT 1 FROM projects WHERE archived_at IS NOT NULL OR deleted_at IS NOT NULL LIMIT 1"
        )
    ):
        raise RuntimeError("已有归档或删除的项目，回退会重新显示这些项目")
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "archived_at")
