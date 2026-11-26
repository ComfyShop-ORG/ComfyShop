"""保存浏览器通知订阅及待投递的任务完成通知。"""

import sqlalchemy as sa
from alembic import op

revision = "f19c73e851da"
down_revision = "2e496d1bc785"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_hash",
            sa.String(64),
            sa.ForeignKey("sessions.token_hash", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(87), nullable=False),
        sa.Column("auth", sa.String(22), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "web_push_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.String(36),
            sa.ForeignKey("web_push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("subscription_id", "task_id", name="uq_web_push_task"),
    )
    op.create_index("ix_web_push_deliveries_task_id", "web_push_deliveries", ["task_id"])
    op.create_index("ix_web_push_deliveries_retry_at", "web_push_deliveries", ["retry_at"])


def downgrade() -> None:
    op.drop_table("web_push_deliveries")
    op.drop_table("web_push_subscriptions")
