"""为账号增加昵称与头像。"""

from alembic import op
import sqlalchemy as sa

revision = "c4a1e35e62f9"
down_revision = "f6a49a5b0d25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("avatar_digest", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("avatar_image", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_image")
    op.drop_column("users", "avatar_digest")
    op.drop_column("users", "nickname")
