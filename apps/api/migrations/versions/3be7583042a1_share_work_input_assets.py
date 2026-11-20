"""在作品中保存作者明确公开的参考素材。"""

from alembic import op
import sqlalchemy as sa

revision = "3be7583042a1"
down_revision = "6bdbfb45b9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("work_id", sa.String(36), sa.ForeignKey("works.id"), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), sa.ForeignKey("media_objects.sha256"), nullable=False),
    )
    op.create_index("ix_work_assets_work_id", "work_assets", ["work_id"])
    op.create_index("ix_work_assets_sha256", "work_assets", ["sha256"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM work_assets LIMIT 1")):
        raise RuntimeError("数据库已有作品公开的参考素材，无法降级后保留这些素材")
    op.drop_table("work_assets")
