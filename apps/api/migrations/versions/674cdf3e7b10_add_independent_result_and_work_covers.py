"""保存执行和作品各自设定的封面图片，并记录新音频的时长。"""

from alembic import op
import sqlalchemy as sa

revision = "674cdf3e7b10"
down_revision = "3be7583042a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_objects", sa.Column("duration_ms", sa.BigInteger(), nullable=True))
    for table in ("executions", "works"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("cover_image_sha256", sa.String(64), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_cover_image_sha256",
                "media_objects",
                ["cover_image_sha256"],
                ["sha256"],
            )
            batch.create_index(f"ix_{table}_cover_image_sha256", ["cover_image_sha256"])


def downgrade() -> None:
    for table in ("works", "executions"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_cover_image_sha256")
            batch.drop_constraint(f"fk_{table}_cover_image_sha256", type_="foreignkey")
            batch.drop_column("cover_image_sha256")
    op.drop_column("media_objects", "duration_ms")
