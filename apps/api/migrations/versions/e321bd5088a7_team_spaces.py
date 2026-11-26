"""保存团队、角色和团队内容归属。"""

import sqlalchemy as sa
from alembic import op

revision = "e321bd5088a7"
down_revision = "f4c03a7b81de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("archived_at", sa.BigInteger()),
    )
    op.create_table(
        "team_members",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(7), nullable=False),
        sa.CheckConstraint("role IN ('reader', 'editor', 'manager', 'owner')", name="team_role"),
    )
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_index(
        "uq_team_owner",
        "team_members",
        ["team_id"],
        unique=True,
        sqlite_where=sa.text("role = 'owner'"),
        postgresql_where=sa.text("role = 'owner'"),
    )
    op.create_table(
        "team_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("record_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_team_events_team_id", "team_events", ["team_id"])
    op.create_table(
        "team_favorites",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id"), primary_key=True),
        sa.Column("added_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
    )
    # 两种数据库都支持带单列外键的 ADD COLUMN，避免为现有记录重建表。
    for name in ("workflows", "assets"):
        op.execute(f"ALTER TABLE {name} ADD COLUMN team_id VARCHAR(36) REFERENCES teams(id)")
    op.create_index("ix_workflows_team_id", "workflows", ["team_id"])
    op.create_index("ix_assets_team_saved", "assets", ["team_id", "saved_at", "id"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM teams LIMIT 1")):
        raise RuntimeError("已有团队记录，回退会丢失团队归属")
    op.drop_index("ix_assets_team_saved", table_name="assets")
    op.drop_index("ix_workflows_team_id", table_name="workflows")
    op.drop_table("team_favorites")
    if op.get_bind().dialect.name == "sqlite":
        for name in ("assets", "workflows"):
            op.execute(f"ALTER TABLE {name} DROP COLUMN team_id")
    else:
        for name in ("assets", "workflows"):
            op.drop_column(name, "team_id")
    op.drop_table("team_events")
    op.drop_table("team_members")
    op.drop_table("teams")
