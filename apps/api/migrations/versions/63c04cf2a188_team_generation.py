"""保存团队任务及作品的空间归属。"""

import sqlalchemy as sa
from alembic import op

revision = "63c04cf2a188"
down_revision = "4c8d0b951e72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("tasks", "works"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN team_id VARCHAR(36) REFERENCES teams(id)")
        op.create_index(f"ix_{table}_team_created", table, ["team_id", "created_at", "id"])


def downgrade() -> None:
    db = op.get_bind()
    for name in ("tasks", "works"):
        table = sa.table(name, sa.column("team_id", sa.String(36)))
        if db.scalar(sa.select(1).where(table.c.team_id.is_not(None)).limit(1)):
            raise RuntimeError("已有团队任务或作品，回退会丢失空间归属")
    for table in ("works", "tasks"):
        op.drop_index(f"ix_{table}_team_created", table_name=table)
        if db.dialect.name == "sqlite":
            op.execute(f"ALTER TABLE {table} DROP COLUMN team_id")
        else:
            op.drop_column(table, "team_id")
