"""音频和模型原件没有图像宽高。"""

from alembic import op
import sqlalchemy as sa

revision = "0d4ae8dbc71c"
down_revision = "e78fbb354f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_objects") as batch:
        batch.alter_column("width", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("height", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT 1 FROM media_objects WHERE width IS NULL OR height IS NULL LIMIT 1")
    ):
        raise RuntimeError("数据库已保存无图像尺寸的原件，无法降级为仅支持图像和视频的结构")
    with op.batch_alter_table("media_objects") as batch:
        batch.alter_column("width", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("height", existing_type=sa.Integer(), nullable=False)
