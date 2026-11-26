"""数据库映射。任务包含多次执行，作品保存选中的成品和允许公开的输入。"""

from enum import StrEnum, nonmember
from time import time_ns
from typing import Literal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ColumnElement,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    SQLColumnExpression,
    String,
    Text,
    UniqueConstraint,
    false,
    select,
)
from sqlalchemy.orm import Mapped, column_property, declared_attr, mapped_column, relationship

from comfyshop_api.core.categories import WorkflowCategory
from comfyshop_api.db import Base


def now_ms() -> int:
    return time_ns() // 1_000_000


def new_id() -> str:
    return str(uuid4())


ComfyStatus = Literal["idle", "busy", "unreachable"]
StartupIssue = Literal["comfy_connection", "comfy_inventory", "platform_connection"]
RecoveryStatus = Literal["uploading", "rerunnable"]


class Status(StrEnum):
    """queued 等待领取，running 已领取并执行或回传。succeeded 已确认成品清单，failed 表示失败。

    cancelled 涵盖排队时取消和执行中停止，只有未领取的任务可恢复排队。
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # 用于查询尚未结束的记录，不作为枚举成员存储或返回。
    ACTIVE = nonmember((QUEUED, RUNNING))


# 两张表均以 VARCHAR(16) 存储小写状态，并在数据库校验取值。
_status_type = Enum(
    Status,
    native_enum=False,
    length=16,
    values_callable=lambda members: [status.value for status in members],
)
_status_check = "status IN (" + ",".join(repr(status.value) for status in Status) + ")"


class SoftDelete:
    """软删除标记。删除只隐藏记录，引用和原文件保留。"""

    deleted_at: Mapped[int | None] = mapped_column(BigInteger)

    @classmethod
    def visible(cls) -> ColumnElement[bool]:
        """查询条件：尚未删除。读取这些表时默认带上，需要读取已删除记录处单独说明。"""
        return cls.deleted_at.is_(None)

    def mark_deleted(self) -> bool:
        """首次删除时记录时间并返回真，重复删除保持原时间。"""
        if self.deleted_at is not None:
            return False
        self.deleted_at = now_ms()
        return True

    def restore(self) -> bool:
        """撤销删除并返回真。记录本来就没有删除时返回假。"""
        if self.deleted_at is None:
            return False
        self.deleted_at = None
        return True


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(32))
    username_key: Mapped[str] = mapped_column(String(64), unique=True)
    official_import_granted: Mapped[bool] = mapped_column(Boolean, server_default=false())
    nickname: Mapped[str | None] = mapped_column(String(32))
    avatar_digest: Mapped[str | None] = mapped_column(String(64))
    avatar_image: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    password_hash: Mapped[str] = mapped_column(Text)
    # 找回密码用的邮箱，可以不填。`email_key` 是比较用的小写形式。
    email: Mapped[str | None] = mapped_column(String(254))
    email_key: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    # 等待邮件确认的邮箱、邮件里一次性凭据的摘要和到期时间。确认后才写入 `email`，
    # 确认前可以与别的账号填写同一个地址。
    pending_email: Mapped[str | None] = mapped_column(String(254))
    pending_email_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    pending_email_expires_at: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    # 注销时间。注销后账号名可被重新注册，本行只为保留其他记录的引用。
    deleted_at: Mapped[int | None] = mapped_column(BigInteger)


class WorkspaceShare(Base):
    __tablename__ = "workspace_shares"
    __table_args__ = (CheckConstraint("owner_id <> viewer_id", name="workspace_share_other_user"),)

    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    viewer_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class TeamRole(StrEnum):
    READER = "reader"
    EDITOR = "editor"
    MANAGER = "manager"
    OWNER = "owner"

    def permits(self, minimum: "TeamRole") -> bool:
        roles = tuple(TeamRole)
        return roles.index(self) >= roles.index(minimum)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    avatar_digest: Mapped[str | None] = mapped_column(String(64))
    avatar_image: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    profile_public: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    archived_at: Mapped[int | None] = mapped_column(BigInteger)

    @classmethod
    def active_scope(cls, team_id: SQLColumnExpression[str | None]) -> ColumnElement[bool]:
        return (
            team_id.is_(None)
            | select(cls.id)
            .where(cls.id == team_id, cls.archived_at.is_(None))
            .correlate_except(cls)
            .exists()
        )


class TeamMember(Base):
    __tablename__ = "team_members"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    role: Mapped[TeamRole] = mapped_column(
        Enum(
            TeamRole,
            native_enum=False,
            values_callable=lambda roles: [role.value for role in roles],
            name="team_role",
            create_constraint=True,
        )
    )
    __table_args__ = (
        Index(
            "uq_team_owner",
            "team_id",
            unique=True,
            sqlite_where=role == TeamRole.OWNER,
            postgresql_where=role == TeamRole.OWNER,
        ),
    )


class TeamEvent(Base):
    """团队管理和内容变更的操作者记录，账号离开或注销后仍保留。"""

    __tablename__ = "team_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (Index("ix_team_events_team_created", "team_id", "created_at", "id"),)


class PasswordReset(Base):
    """找回密码的一次性凭据。邮件里是原值，这里只保存摘要。"""

    __tablename__ = "password_resets"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    user: Mapped[User] = relationship()


class WebPushSubscription(Base):
    """浏览器推送绑定登录会话。退出或替换会话时，订阅和未发送通知一起失效。"""

    __tablename__ = "web_push_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_hash: Mapped[str] = mapped_column(
        ForeignKey("sessions.token_hash", ondelete="CASCADE"), unique=True
    )
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True)
    endpoint: Mapped[str] = mapped_column(Text)
    p256dh: Mapped[str] = mapped_column(String(87))
    auth: Mapped[str] = mapped_column(String(22))
    language: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[int | None] = mapped_column(BigInteger)


class WebPushDelivery(Base):
    __tablename__ = "web_push_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("web_push_subscriptions.id", ondelete="CASCADE")
    )
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    retry_at: Mapped[int] = mapped_column(BigInteger, index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint("subscription_id", "task_id", name="uq_web_push_task"),)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger)
    attempts: Mapped[int]


class Project(SoftDelete, Base):
    """同一空间内的一项工作，素材和工作流通过引用关联。"""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_owner_created", "owner_id", "team_id", "created_at", "id"),
        Index("ix_projects_team_created", "team_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(480))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    archived_at: Mapped[int | None] = mapped_column(BigInteger)


class ProjectWorkflow(Base):
    __tablename__ = "project_workflows"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class ProjectAsset(Base):
    __tablename__ = "project_assets"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Workflow(SoftDelete, Base):
    """工作流名称、所有者和发布指针，实际图谱由 `WorkflowVersion` 保存。"""

    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    official_key: Mapped[str | None] = mapped_column(String(120))
    remote_source: Mapped[str | None] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[WorkflowCategory] = mapped_column(String(32), default=WorkflowCategory.IMAGE)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_version_id: Mapped[str | None] = mapped_column(String(36))
    # 作者指定的作品可覆盖作者上传的图片，取消指定时保留图片。
    cover_work_id: Mapped[str | None] = mapped_column(String(36))
    # 作者上传的图片。官方模型的默认图按标识另存。
    default_cover_sha256: Mapped[str | None] = mapped_column(
        ForeignKey("media_objects.sha256", name="fk_workflows_default_cover_sha256"), index=True
    )
    # 作者写给访客的简介，说明这个工作流做什么、需要准备什么。
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    owner: Mapped[User] = relationship(lazy="joined")
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        order_by="WorkflowVersion.number", lazy="selectin"
    )
    __table_args__ = (
        Index("ix_workflows_remote_source", "owner_id", "remote_source"),
        Index("ix_workflows_official_key", "official_key", unique=True),
        Index(
            "ix_workflows_public_updated",
            "published",
            "deleted_at",
            "updated_at",
            "id",
        ),
        CheckConstraint(
            "category IN (" + ",".join(repr(item.value) for item in WorkflowCategory) + ")",
            name="workflow_category",
        ),
    )

    @classmethod
    def publicly_visible(cls) -> ColumnElement[bool]:
        return cls.visible() & cls.published.is_(True) & Team.active_scope(cls.team_id)


class WorkflowVersion(Base):
    """一个版本的图谱、参数展示配置和发布状态。"""

    __tablename__ = "workflow_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    number: Mapped[int]
    graph: Mapped[dict] = mapped_column(JSON, deferred=True)
    graph_hash: Mapped[str] = mapped_column(String(64))
    translations: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    parameter_layout: Mapped[list[dict] | None] = mapped_column(
        JSON(none_as_null=True), deferred=True
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    worker_kind: Mapped[str] = mapped_column(
        String(40), default="comfyui", server_default="comfyui"
    )
    connection_scope: Mapped[str | None] = mapped_column(String(80))
    worker_data: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), deferred=True)
    format: Mapped[Literal["api", "ui", "service", "remote"]] = mapped_column(String(8))
    requirements: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint("workflow_id", "number", name="uq_workflow_version_number"),)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), primary_key=True)


class TeamFavorite(Base):
    __tablename__ = "team_favorites"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), primary_key=True)
    added_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Machine(SoftDelete, Base):
    """撤销后可从管理列表删除，历史任务保留工作机引用。"""

    __tablename__ = "machines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    worker_kind: Mapped[str] = mapped_column(
        String(40), default="comfyui", server_default="comfyui"
    )
    connection_scope: Mapped[str | None] = mapped_column(String(80))
    credential: Mapped[str | None] = mapped_column(Text, deferred=True)
    connection_revision: Mapped[str | None] = mapped_column(String(36))
    device: Mapped[str] = mapped_column(String(200), default="")
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_info: Mapped[dict | None] = mapped_column(JSON)
    update_info: Mapped[dict | None] = mapped_column(JSON)
    # 列表和详情轮询只读节点数量，工作流表单按需读取完整目录。
    catalog: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", deferred=True)
    catalog_hash: Mapped[str | None] = mapped_column(String(64))
    catalog_synced_at: Mapped[int | None] = mapped_column(BigInteger)
    comfy_status: Mapped[ComfyStatus | None] = mapped_column(String(16))
    startup_issue: Mapped[StartupIssue | None] = mapped_column(String(24))
    startup_issue_at: Mapped[int | None] = mapped_column(BigInteger)
    last_seen: Mapped[int | None] = mapped_column(BigInteger)
    busy_until: Mapped[int] = mapped_column(BigInteger, default=0)
    paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger)


class Task(SoftDelete, Base):
    """一次网页提交的任务批次，包含提交时冻结的版本、参数和工作机租约。"""

    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"))
    workflow_name: Mapped[str] = mapped_column(String(120))
    execution_count: Mapped[int] = mapped_column(default=1)
    input_values: Mapped[dict] = mapped_column(JSON)
    input_schema: Mapped[dict] = mapped_column(JSON)
    input_graph: Mapped[dict] = mapped_column(JSON, deferred=True)
    status: Mapped[Status] = mapped_column(_status_type, default=Status.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"), index=True)
    # 随任务读取，包含已从管理列表移除的工作机。
    machine_name: Mapped[str | None] = column_property(
        select(Machine.name)
        .where(Machine.id == machine_id)
        .correlate_except(Machine)
        .scalar_subquery()
    )
    worker_kind: Mapped[str] = mapped_column(
        String(40), default="comfyui", server_default="comfyui"
    )
    connection_revision: Mapped[str | None] = mapped_column(String(36))
    worker_data: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    cloud_cancel: Mapped[Literal["not_submitted", "accepted", "unconfirmed"] | None] = (
        mapped_column(String(16))
    )
    official_taken_over: Mapped[bool] = mapped_column(Boolean, server_default=false())
    claim_id: Mapped[str | None] = mapped_column(String(36))
    lease_hash: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[int | None] = mapped_column(BigInteger)
    event_seq: Mapped[int] = mapped_column(default=0, server_default="0")
    stage: Mapped[str] = mapped_column(String(24), default="queued", server_default="queued")
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    source_execution_id: Mapped[str | None] = mapped_column(
        ForeignKey("executions.id", name="fk_tasks_source_execution", use_alter=True)
    )
    source_work_id: Mapped[str | None] = mapped_column(
        ForeignKey("works.id", name="fk_tasks_source_work", use_alter=True)
    )
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    queued_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_task_idempotency"),
        UniqueConstraint("claim_id", name="uq_task_claim"),
        CheckConstraint(_status_check, name="task_status"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="task_progress"),
        CheckConstraint("execution_count BETWEEN 1 AND 32", name="task_execution_count"),
        Index("ix_tasks_owner_created", "owner_id", "created_at", "id"),
        Index("ix_tasks_team_created", "team_id", "created_at", "id"),
        Index("ix_tasks_project_created", "project_id", "created_at", "id"),
        # 私有封面按工作流和所有者找任务，读取量取决于这个工作流自己的任务数。
        Index("ix_tasks_workflow_owner", "workflow_id", "owner_id"),
        # 后台和每次领取都要找租约到期的执行中任务，不能扫描全部历史任务。
        Index("ix_tasks_status_lease", "status", "lease_expires_at"),
        Index("ix_tasks_machine_queue", "machine_id", "status", "queued_at", "id"),
        Index("ix_tasks_worker_dispatch", "worker_kind", "status", "queued_at", "id"),
    )


class OfficialTakeoverWait(Base):
    """任务租约到期后的一段已结束等待，按任务内序号保存。"""

    __tablename__ = "official_takeover_waits"
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[int] = mapped_column(BigInteger)
    ended_at: Mapped[int] = mapped_column(BigInteger)
    outcome: Mapped[Literal["resumed", "ended"]] = mapped_column(String(8))
    __table_args__ = (
        CheckConstraint("number > 0 AND ended_at >= started_at", name="official_wait_interval"),
        CheckConstraint("outcome IN ('resumed', 'ended')", name="official_wait_outcome"),
    )


class MachineLink(Base):
    """没有密钥的工作机提交的接入申请。

    工作机保存 `secret_hash` 的原值，网页用 `code` 找到申请。确认后写入操作者 `owner_id` 和空间 `team_id`，
    重新连接时还记下 `reconnect_machine_id`。工作机凭原值换取密钥后写入 `machine_id`。
    回复丢失时，工作机在申请到期前凭同一原值重试，平台为同一台工作机换发密钥。
    """

    __tablename__ = "machine_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    # 申请来自的网络地址，确认页据此提示申请是否来自当前浏览器所在的网络。
    source_ip: Mapped[str] = mapped_column(String(64), default="", server_default="")
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))
    reconnect_machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    default_machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))


class TeamMachinePreference(Base):
    __tablename__ = "team_machine_preferences"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    default_machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))


class MediaObject(Base):
    """原件登记。素材、成品、封面和作品输入的外键决定原件何时可以回收。"""

    __tablename__ = "media_objects"
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    storage_name: Mapped[str] = mapped_column(String(96), unique=True)
    size: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(80))
    width: Mapped[int | None]
    height: Mapped[int | None]
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)


class OfficialWorkflowCover(Base):
    """各站同一官方模型共用的默认图。"""

    __tablename__ = "official_workflow_covers"
    official_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    sha256: Mapped[str] = mapped_column(ForeignKey("media_objects.sha256"), index=True)


class OfficialWorkerPoll(Base):
    """按适配器记录最近一次经过认证的官方工作机接单请求。"""

    __tablename__ = "official_worker_polls"
    adapter: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_polled_at: Mapped[int] = mapped_column(BigInteger)


class OriginalDeletion(Base):
    """后台待回收的原件存储名。"""

    __tablename__ = "original_deletions"
    storage_name: Mapped[str] = mapped_column(String(96), primary_key=True)
    retry_at: Mapped[int] = mapped_column(BigInteger, index=True)


class MediaRecord:
    """业务记录保留各自的文件名和 MIME，原件按字节复用。"""

    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(ForeignKey("media_objects.sha256"), index=True)
    content_type: Mapped[str] = mapped_column(String(80))

    @declared_attr
    def media(cls) -> Mapped[MediaObject]:
        return relationship(MediaObject, lazy="joined", innerjoin=True)


class StoredMedia(MediaRecord):
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Artifact(SoftDelete, StoredMedia, Base):
    """一次执行的输出文件，记录输出节点、输出槽与组内顺序。"""

    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    client_id: Mapped[str] = mapped_column(String(64))
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    output_node_id: Mapped[str] = mapped_column(String(120), default="", server_default="")
    output_node_title: Mapped[str] = mapped_column(String(160), default="", server_default="")
    output_slot: Mapped[str] = mapped_column(String(256), default="", server_default="")
    output_index: Mapped[int] = mapped_column(default=0, server_default="0")
    __table_args__ = (UniqueConstraint("task_id", "client_id", name="uq_artifact_upload"),)


class Execution(Base):
    """任务批次中的一次完整运行，`index` 从 0 起，成功时保存有序成品清单。"""

    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    index: Mapped[int]
    input_values: Mapped[dict] = mapped_column(JSON)
    status: Mapped[Status] = mapped_column(_status_type, default=Status.QUEUED)
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    submission_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    recovery_status: Mapped[RecoveryStatus | None] = mapped_column(String(16))
    retry_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", name="fk_execution_retry_task")
    )
    effective_prompt: Mapped[str | None] = mapped_column(Text)
    manifest: Mapped[list | None] = mapped_column(JSON)
    # 所有者指定的组封面成品。为空或该成品已删除时，从本组剩余成品中选取。
    cover_artifact_id: Mapped[str | None] = mapped_column(String(36))
    # 封面是视频时取哪一刻的画面，单位毫秒。为空时用首帧。
    cover_frame_ms: Mapped[int | None] = mapped_column(BigInteger)
    cover_image_sha256: Mapped[str | None] = mapped_column(
        ForeignKey("media_objects.sha256"), index=True
    )
    cover_image: Mapped[MediaObject | None] = relationship(lazy="joined")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (
        Index(
            "ix_executions_status_updated",
            "status",
            "updated_at",
            "id",
        ),
        UniqueConstraint("task_id", "index", name="uq_execution_index"),
        CheckConstraint('"index" BETWEEN 0 AND 31', name="execution_index"),
        CheckConstraint(_status_check, name="execution_status"),
    )


class Work(SoftDelete, Base):
    """从成功执行发布的作品，固定来源版本、封面和允许共享的参数。"""

    __tablename__ = "works"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"))
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    # 作者发布时写的说明，随作品公开。
    description: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(String(64))
    cover_artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    # 封面是视频时取哪一刻的画面，单位毫秒。为空时用首帧。
    cover_frame_ms: Mapped[int | None] = mapped_column(BigInteger)
    cover_image_sha256: Mapped[str | None] = mapped_column(
        ForeignKey("media_objects.sha256"), index=True
    )
    cover_image: Mapped[MediaObject | None] = relationship(lazy="joined")
    input_values: Mapped[dict] = mapped_column(JSON, default=dict)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (
        Index("ix_works_team_created", "team_id", "created_at", "id"),
        Index(
            "ix_works_workflow_owner_public_created",
            "workflow_id",
            "owner_id",
            "published",
            "deleted_at",
            "created_at",
            "id",
        ),
    )


class WorkArtifact(Base):
    __tablename__ = "work_artifacts"
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), primary_key=True)
    position: Mapped[int]
    __table_args__ = (UniqueConstraint("work_id", "position", name="uq_work_artifact_position"),)


class WorkAsset(MediaRecord, Base):
    """随作品公开的参考文件。授权和文件名取自发布时的输入快照。"""

    __tablename__ = "work_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)


class Asset(StoredMedia, Base):
    """私有输入素材。保存到资产库的素材拥有独立于任务的保留期。"""

    __tablename__ = "assets"
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    saved_at: Mapped[int | None] = mapped_column(BigInteger)
    __table_args__ = (
        Index("ix_assets_created", "created_at", "id"),
        Index("ix_assets_owner_saved", "owner_id", "saved_at", "id"),
        Index("ix_assets_team_saved", "team_id", "saved_at", "id"),
    )


class TaskAsset(Base):
    __tablename__ = "task_assets"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    input_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
