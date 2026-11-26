"""为团队操作记录的倒序分页建立索引。"""

from alembic import op

revision = "835d20859320"
down_revision = "4f7c1a032ce5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_team_events_team_created", "team_events", ["team_id", "created_at", "id"])
    op.drop_index("ix_team_events_team_id", table_name="team_events")


def downgrade() -> None:
    op.create_index("ix_team_events_team_id", "team_events", ["team_id"])
    op.drop_index("ix_team_events_team_created", table_name="team_events")
