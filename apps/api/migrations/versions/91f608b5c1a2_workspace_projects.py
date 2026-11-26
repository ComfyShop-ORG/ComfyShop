"""保存空间项目、项目资料引用和生成任务的项目归属。"""

import sqlalchemy as sa
from alembic import op

revision = "91f608b5c1a2"
down_revision = "835d20859320"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(480), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_projects_owner_created", "projects", ["owner_id", "team_id", "created_at", "id"]
    )
    op.create_index("ix_projects_team_created", "projects", ["team_id", "created_at", "id"])
    for kind, item, target in (
        ("project_workflows", "workflow_id", "workflows"),
        ("project_assets", "asset_id", "assets"),
    ):
        op.create_table(
            kind,
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                item,
                sa.String(36),
                sa.ForeignKey(f"{target}.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )
        op.create_index(f"ix_{kind}_{item}", kind, [item])
    op.execute("ALTER TABLE tasks ADD COLUMN project_id VARCHAR(36) REFERENCES projects(id)")
    op.create_index("ix_tasks_project_created", "tasks", ["project_id", "created_at", "id"])


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(sa.select(1).select_from(sa.table("projects")).limit(1)):
        raise RuntimeError("已有空间项目，回退会丢失项目资料和任务归属")
    op.drop_index("ix_tasks_project_created", table_name="tasks")
    if db.dialect.name == "sqlite":
        op.execute("ALTER TABLE tasks DROP COLUMN project_id")
    else:
        op.drop_column("tasks", "project_id")
    op.drop_table("project_assets")
    op.drop_table("project_workflows")
    op.drop_table("projects")
