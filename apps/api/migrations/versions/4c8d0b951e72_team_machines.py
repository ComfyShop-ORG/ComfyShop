"""保存团队工作机、接入申请和默认工作机。"""

import sqlalchemy as sa
from alembic import op

revision = "4c8d0b951e72"
down_revision = "e321bd5088a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("machines", "machine_links"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN team_id VARCHAR(36) REFERENCES teams(id)")
    op.create_index("ix_machines_team_id", "machines", ["team_id"])
    op.create_table(
        "team_machine_preferences",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), primary_key=True),
        sa.Column("default_machine_id", sa.String(36), sa.ForeignKey("machines.id")),
    )


def downgrade() -> None:
    db = op.get_bind()
    for name in ("machines", "machine_links"):
        table = sa.table(name, sa.column("team_id", sa.String(36)))
        if db.scalar(sa.select(1).where(table.c.team_id.is_not(None)).limit(1)):
            raise RuntimeError("已有团队工作机或接入申请，回退会丢失空间归属")
    op.drop_table("team_machine_preferences")
    op.drop_index("ix_machines_team_id", table_name="machines")
    for table in ("machine_links", "machines"):
        if db.dialect.name == "sqlite":
            op.execute(f"ALTER TABLE {table} DROP COLUMN team_id")
        else:
            op.drop_column(table, "team_id")
