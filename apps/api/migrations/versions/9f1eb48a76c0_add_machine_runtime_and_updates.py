"""保存工作机上报的运行版本和用户请求的更新状态。"""

from alembic import op
import sqlalchemy as sa

revision = "9f1eb48a76c0"
down_revision = "674cdf3e7b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("machines", sa.Column("runtime_info", sa.JSON(), nullable=True))
    op.add_column("machines", sa.Column("update_info", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("machines", "update_info")
    op.drop_column("machines", "runtime_info")
