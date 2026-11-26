"""保存团队自定义头像。"""

import sqlalchemy as sa
from alembic import op

revision = "0a20425c6fa2"
down_revision = "63c04cf2a188"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("avatar_digest", sa.String(64)))
    op.add_column("teams", sa.Column("avatar_image", sa.LargeBinary()))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM teams WHERE avatar_image IS NOT NULL LIMIT 1")):
        raise RuntimeError("已有团队自定义头像，回退会丢失图片")
    op.drop_column("teams", "avatar_image")
    op.drop_column("teams", "avatar_digest")
