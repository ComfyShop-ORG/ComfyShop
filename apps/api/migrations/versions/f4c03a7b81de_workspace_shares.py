"""授权其他账号只读访问个人空间。"""

import sqlalchemy as sa
from alembic import op

revision = "f4c03a7b81de"
down_revision = "490d562f6d9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_shares",
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("viewer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.PrimaryKeyConstraint("owner_id", "viewer_id"),
        sa.CheckConstraint("owner_id <> viewer_id", name="workspace_share_other_user"),
    )
    op.create_index("ix_workspace_shares_viewer_id", "workspace_shares", ["viewer_id"])


def downgrade() -> None:
    op.drop_table("workspace_shares")
