"""接入申请可以重新连接已有工作机。"""

from alembic import op
import sqlalchemy as sa

revision = "6bdbfb45b9c1"
down_revision = "0d4ae8dbc71c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("machine_links") as batch:
        batch.add_column(sa.Column("reconnect_machine_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_machine_links_reconnect_machine_id", "machines", ["reconnect_machine_id"], ["id"]
        )


def downgrade() -> None:
    op.execute("DELETE FROM machine_links WHERE reconnect_machine_id IS NOT NULL")
    with op.batch_alter_table("machine_links") as batch:
        batch.drop_constraint("fk_machine_links_reconnect_machine_id", type_="foreignkey")
        batch.drop_column("reconnect_machine_id")
