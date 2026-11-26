"""创建 ComfyShop 的初始表、索引和约束。"""

import sqlalchemy as sa
from alembic import op

revision = "d522fa8dee69"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_attempts",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "media_objects",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_name", sa.String(length=96), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("sha256"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_table(
        "official_worker_polls",
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("last_polled_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("adapter"),
    )
    op.create_table(
        "original_deletions",
        sa.Column("storage_name", sa.String(length=96), nullable=False),
        sa.Column("retry_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("storage_name"),
    )
    op.create_index(
        op.f("ix_original_deletions_retry_at"), "original_deletions", ["retry_at"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("username_key", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=32), nullable=True),
        sa.Column("avatar_digest", sa.String(length=64), nullable=True),
        sa.Column("avatar_image", sa.LargeBinary(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_key", sa.String(length=254), nullable=True),
        sa.Column("pending_email", sa.String(length=254), nullable=True),
        sa.Column("pending_email_token", sa.String(length=64), nullable=True),
        sa.Column("pending_email_expires_at", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username_key"),
    )
    op.create_index(op.f("ix_users_email_key"), "users", ["email_key"], unique=True)
    op.create_index(
        op.f("ix_users_pending_email_token"), "users", ["pending_email_token"], unique=True
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sha256"],
            ["media_objects.sha256"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_created", "assets", ["created_at", "id"], unique=False)
    op.create_index(op.f("ix_assets_owner_id"), "assets", ["owner_id"], unique=False)
    op.create_index(op.f("ix_assets_sha256"), "assets", ["sha256"], unique=False)
    op.create_table(
        "machines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("worker_kind", sa.String(length=40), server_default="comfyui", nullable=False),
        sa.Column("connection_scope", sa.String(length=80), nullable=True),
        sa.Column("credential", sa.Text(), nullable=True),
        sa.Column("connection_revision", sa.String(length=36), nullable=True),
        sa.Column("device", sa.String(length=200), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("runtime_info", sa.JSON(), nullable=True),
        sa.Column("update_info", sa.JSON(), nullable=True),
        sa.Column("catalog", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("catalog_hash", sa.String(length=64), nullable=True),
        sa.Column("catalog_synced_at", sa.BigInteger(), nullable=True),
        sa.Column("comfy_status", sa.String(length=16), nullable=True),
        sa.Column("startup_issue", sa.String(length=24), nullable=True),
        sa.Column("startup_issue_at", sa.BigInteger(), nullable=True),
        sa.Column("last_seen", sa.BigInteger(), nullable=True),
        sa.Column("busy_until", sa.BigInteger(), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_machines_owner_id"), "machines", ["owner_id"], unique=False)
    op.create_table(
        "official_workflow_covers",
        sa.Column("official_key", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["sha256"],
            ["media_objects.sha256"],
        ),
        sa.PrimaryKeyConstraint("official_key"),
    )
    op.create_index(
        op.f("ix_official_workflow_covers_sha256"),
        "official_workflow_covers",
        ["sha256"],
        unique=False,
    )
    op.create_table(
        "password_resets",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_password_resets_user_id"), "password_resets", ["user_id"], unique=False
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("site", sa.String(length=32), server_default="zh", nullable=False),
        sa.Column("official_key", sa.String(length=120), nullable=True),
        sa.Column("remote_source", sa.String(length=256), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("published_version_id", sa.String(length=36), nullable=True),
        sa.Column("cover_work_id", sa.String(length=36), nullable=True),
        sa.Column("default_cover_sha256", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "category IN ('image','image_tool','video','video_tool','audio','3d','vector','llm','node_basics','product_ads','character_fashion','brand_design')",
            name="workflow_category",
        ),
        sa.ForeignKeyConstraint(
            ["default_cover_sha256"],
            ["media_objects.sha256"],
            name="fk_workflows_default_cover_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workflows_default_cover_sha256"),
        "workflows",
        ["default_cover_sha256"],
        unique=False,
    )
    op.create_index(op.f("ix_workflows_owner_id"), "workflows", ["owner_id"], unique=False)
    op.create_index(
        "ix_workflows_remote_source",
        "workflows",
        ["owner_id", "site", "remote_source"],
        unique=False,
    )
    op.create_index(
        "ix_workflows_site_official_key", "workflows", ["site", "official_key"], unique=True
    )
    op.create_index(
        "ix_workflows_site_public_updated",
        "workflows",
        ["site", "published", "deleted_at", "updated_at", "id"],
        unique=False,
    )
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "workflow_id"),
    )
    op.create_table(
        "machine_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("source_ip", sa.String(length=64), server_default="", nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=True),
        sa.Column("reconnect_machine_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reconnect_machine_id"],
            ["machines.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("secret_hash"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("default_machine_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["default_machine_id"],
            ["machines.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("graph_hash", sa.String(length=64), nullable=False),
        sa.Column("parameter_layout", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("worker_kind", sa.String(length=40), server_default="comfyui", nullable=False),
        sa.Column("connection_scope", sa.String(length=80), nullable=True),
        sa.Column("worker_data", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "number", name="uq_workflow_version_number"),
    )
    op.create_index(
        op.f("ix_workflow_versions_workflow_id"), "workflow_versions", ["workflow_id"], unique=False
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_name", sa.String(length=120), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False),
        sa.Column("input_values", sa.JSON(), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("input_graph", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.String(length=36), nullable=True),
        sa.Column("worker_kind", sa.String(length=40), server_default="comfyui", nullable=False),
        sa.Column("connection_revision", sa.String(length=36), nullable=True),
        sa.Column("worker_data", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("cloud_cancel", sa.String(length=16), nullable=True),
        sa.Column("official_taken_over", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=True),
        sa.Column("lease_hash", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.BigInteger(), nullable=True),
        sa.Column("event_seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stage", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("prompt_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("source_execution_id", sa.String(length=36), nullable=True),
        sa.Column("source_work_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("queued_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="task_status"
        ),
        sa.CheckConstraint("execution_count BETWEEN 1 AND 32", name="task_execution_count"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="task_progress"),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_execution_id"],
            ["executions.id"],
            name="fk_tasks_source_execution",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["source_work_id"], ["works.id"], name="fk_tasks_source_work", use_alter=True
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["workflow_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", name="uq_task_claim"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_task_idempotency"),
    )
    op.create_index(op.f("ix_tasks_machine_id"), "tasks", ["machine_id"], unique=False)
    op.create_index(
        "ix_tasks_machine_queue", "tasks", ["machine_id", "status", "queued_at", "id"], unique=False
    )
    op.create_index(
        "ix_tasks_owner_created", "tasks", ["owner_id", "created_at", "id"], unique=False
    )
    op.create_index(op.f("ix_tasks_owner_id"), "tasks", ["owner_id"], unique=False)
    op.create_index("ix_tasks_status_lease", "tasks", ["status", "lease_expires_at"], unique=False)
    op.create_index(
        "ix_tasks_worker_dispatch",
        "tasks",
        ["worker_kind", "status", "queued_at", "id"],
        unique=False,
    )
    op.create_index(op.f("ix_tasks_workflow_id"), "tasks", ["workflow_id"], unique=False)
    op.create_index("ix_tasks_workflow_owner", "tasks", ["workflow_id", "owner_id"], unique=False)
    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("input_values", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("prompt_id", sa.String(length=64), nullable=True),
        sa.Column("submission_pending", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("recovery_status", sa.String(length=16), nullable=True),
        sa.Column("retry_task_id", sa.String(length=36), nullable=True),
        sa.Column("effective_prompt", sa.Text(), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("cover_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("cover_frame_ms", sa.BigInteger(), nullable=True),
        sa.Column("cover_image_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="execution_status",
        ),
        sa.CheckConstraint('"index" BETWEEN 0 AND 31', name="execution_index"),
        sa.ForeignKeyConstraint(
            ["cover_image_sha256"],
            ["media_objects.sha256"],
        ),
        sa.ForeignKeyConstraint(["retry_task_id"], ["tasks.id"], name="fk_execution_retry_task"),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "index", name="uq_execution_index"),
    )
    op.create_index(
        op.f("ix_executions_cover_image_sha256"), "executions", ["cover_image_sha256"], unique=False
    )
    op.create_index(
        "ix_executions_status_updated", "executions", ["status", "updated_at", "id"], unique=False
    )
    op.create_index(op.f("ix_executions_task_id"), "executions", ["task_id"], unique=False)
    op.create_table(
        "official_takeover_waits",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.CheckConstraint("outcome IN ('resumed', 'ended')", name="official_wait_outcome"),
        sa.CheckConstraint("number > 0 AND ended_at >= started_at", name="official_wait_interval"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "number"),
    )
    op.create_table(
        "task_assets",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=120), nullable=False),
        sa.Column("input_name", sa.String(length=256), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("task_id", "node_id", "input_name"),
    )
    op.create_index(op.f("ix_task_assets_asset_id"), "task_assets", ["asset_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("output_node_id", sa.String(length=120), server_default="", nullable=False),
        sa.Column("output_node_title", sa.String(length=160), server_default="", nullable=False),
        sa.Column("output_slot", sa.String(length=256), server_default="", nullable=False),
        sa.Column("output_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sha256"],
            ["media_objects.sha256"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "client_id", name="uq_artifact_upload"),
    )
    op.create_index(op.f("ix_artifacts_execution_id"), "artifacts", ["execution_id"], unique=False)
    op.create_index(op.f("ix_artifacts_owner_id"), "artifacts", ["owner_id"], unique=False)
    op.create_index(op.f("ix_artifacts_sha256"), "artifacts", ["sha256"], unique=False)
    op.create_index(op.f("ix_artifacts_task_id"), "artifacts", ["task_id"], unique=False)
    op.create_table(
        "works",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("cover_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("cover_frame_ms", sa.BigInteger(), nullable=True),
        sa.Column("cover_image_sha256", sa.String(length=64), nullable=True),
        sa.Column("input_values", sa.JSON(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cover_artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["cover_image_sha256"],
            ["media_objects.sha256"],
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["workflow_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_works_cover_image_sha256"), "works", ["cover_image_sha256"], unique=False
    )
    op.create_index(op.f("ix_works_execution_id"), "works", ["execution_id"], unique=False)
    op.create_index(op.f("ix_works_owner_id"), "works", ["owner_id"], unique=False)
    op.create_index(op.f("ix_works_workflow_id"), "works", ["workflow_id"], unique=False)
    op.create_index(
        "ix_works_workflow_owner_public_created",
        "works",
        ["workflow_id", "owner_id", "published", "deleted_at", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "work_artifacts",
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["works.id"],
        ),
        sa.PrimaryKeyConstraint("work_id", "artifact_id"),
        sa.UniqueConstraint("work_id", "position", name="uq_work_artifact_position"),
    )
    op.create_table(
        "work_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["sha256"],
            ["media_objects.sha256"],
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["works.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_assets_sha256"), "work_assets", ["sha256"], unique=False)
    op.create_index(op.f("ix_work_assets_work_id"), "work_assets", ["work_id"], unique=False)

    # SQLite 随表声明循环外键，PostgreSQL 需要先建好执行和作品表。
    if op.get_context().dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_tasks_source_execution", "tasks", "executions", ["source_execution_id"], ["id"]
        )
        op.create_foreign_key("fk_tasks_source_work", "tasks", "works", ["source_work_id"], ["id"])


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.drop_constraint("fk_tasks_source_work", "tasks", type_="foreignkey")
        op.drop_constraint("fk_tasks_source_execution", "tasks", type_="foreignkey")
    op.drop_table("work_assets")
    op.drop_table("work_artifacts")
    op.drop_table("works")
    op.drop_table("artifacts")
    op.drop_table("task_assets")
    op.drop_table("official_takeover_waits")
    op.drop_table("executions")
    op.drop_table("tasks")
    op.drop_table("workflow_versions")
    op.drop_table("user_preferences")
    op.drop_table("machine_links")
    op.drop_table("favorites")
    op.drop_table("workflows")
    op.drop_table("sessions")
    op.drop_table("password_resets")
    op.drop_table("official_workflow_covers")
    op.drop_table("machines")
    op.drop_table("assets")
    op.drop_table("users")
    op.drop_table("original_deletions")
    op.drop_table("official_worker_polls")
    op.drop_table("media_objects")
    op.drop_table("auth_attempts")
