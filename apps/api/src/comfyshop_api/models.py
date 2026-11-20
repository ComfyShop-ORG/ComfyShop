"""数据库映射。任务包含多次执行，作品保存选中的成品和允许公开的输入。"""

from time import time_ns
from typing import Final, Literal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import ColumnElement
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from comfyshop_api.core.categories import WorkflowCategory, WorkflowCategoryFilter
from comfyshop_api.db import Base


def now_ms() -> int:
    return time_ns() // 1_000_000


def new_id() -> str:
    return str(uuid4())


StatusValue = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class Status:
    """任务与执行共用的状态值。数据库约束和 API 契约使用相同的字符串。"""

    QUEUED: Final = "queued"
    RUNNING: Final = "running"
    SUCCEEDED: Final = "succeeded"
    FAILED: Final = "failed"
    CANCELLED: Final = "cancelled"
    # 尚未结束，仍可能被工作机领取或推进。
    ACTIVE: Final = (QUEUED, RUNNING)


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


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger)
    attempts: Mapped[int]


class Workflow(SoftDelete, Base):
    """工作流名称、所有者和发布指针，实际图谱由 `WorkflowVersion` 保存。"""

    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[WorkflowCategory] = mapped_column(String(16), default=WorkflowCategory.IMAGE)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_version_id: Mapped[str | None] = mapped_column(String(36))
    # 作者指定用作封面的作品。为空或该作品不再公开时，取作者最近公开的作品。
    cover_work_id: Mapped[str | None] = mapped_column(String(36))
    # 作者写给访客的简介，说明这个工作流做什么、需要准备什么。
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    owner: Mapped[User] = relationship(lazy="joined")
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        order_by="WorkflowVersion.number", lazy="selectin"
    )
    __table_args__ = (
        CheckConstraint(
            "category IN (" + ",".join(repr(item.value) for item in WorkflowCategory) + ")",
            name="workflow_category",
        ),
    )

    @classmethod
    def in_category(cls, category: WorkflowCategoryFilter) -> ColumnElement[bool]:
        if category == "tool":
            return cls.category.in_((WorkflowCategory.IMAGE_TOOL, WorkflowCategory.VIDEO_TOOL))
        return cls.category == category


class WorkflowVersion(Base):
    """一个版本的图谱、参数展示配置和发布状态。"""

    __tablename__ = "workflow_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    number: Mapped[int]
    graph: Mapped[dict] = mapped_column(JSON, deferred=True)
    graph_hash: Mapped[str] = mapped_column(String(64))
    parameter_layout: Mapped[list[dict] | None] = mapped_column(
        JSON(none_as_null=True), deferred=True
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    format: Mapped[Literal["api", "ui"]] = mapped_column(String(8))
    requirements: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint("workflow_id", "number", name="uq_workflow_version_number"),)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), primary_key=True)


class Task(SoftDelete, Base):
    """一次网页提交的任务批次，包含提交时冻结的版本、参数和工作机租约。"""

    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"))
    workflow_name: Mapped[str] = mapped_column(String(120))
    execution_count: Mapped[int] = mapped_column(default=1)
    input_values: Mapped[dict] = mapped_column(JSON)
    input_schema: Mapped[dict] = mapped_column(JSON)
    input_graph: Mapped[dict] = mapped_column(JSON, deferred=True)
    status: Mapped[StatusValue] = mapped_column(String(16), default=Status.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"), index=True)
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
        ForeignKey("executions.id", use_alter=True)
    )
    source_work_id: Mapped[str | None] = mapped_column(ForeignKey("works.id", use_alter=True))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_task_idempotency"),
        UniqueConstraint("claim_id", name="uq_task_claim"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="task_status"
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="task_progress"),
        CheckConstraint("execution_count BETWEEN 1 AND 32", name="task_execution_count"),
        Index("ix_tasks_owner_created", "owner_id", "created_at", "id"),
        # 私有封面按工作流和所有者找任务，读取量取决于这个工作流自己的任务数。
        Index("ix_tasks_workflow_owner", "workflow_id", "owner_id"),
        # 后台和每次领取都要找租约到期的执行中任务，不能扫描全部历史任务。
        Index("ix_tasks_status_lease", "status", "lease_expires_at"),
    )


class Machine(Base):
    __tablename__ = "machines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    device: Mapped[str] = mapped_column(String(200), default="")
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    catalog: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    catalog_hash: Mapped[str | None] = mapped_column(String(64))
    last_seen: Mapped[int | None] = mapped_column(BigInteger)
    busy_until: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger)


class MachineLink(Base):
    """没有密钥的工作机提交的接入申请。

    工作机保存 `secret_hash` 的原值，网页用 `code` 找到申请。账号确认后写入 `owner_id`，
    重新连接时还记下 `reconnect_machine_id`。工作机凭原值换取密钥后写入 `machine_id`。
    回复丢失时，工作机在申请到期前凭同一原值重试，平台为同一台工作机换发密钥。
    """

    __tablename__ = "machine_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
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


class OriginalDeletion(Base):
    """后台待回收的原件存储名。"""

    __tablename__ = "original_deletions"
    storage_name: Mapped[str] = mapped_column(String(96), primary_key=True)
    retry_at: Mapped[int] = mapped_column(BigInteger, index=True)


class MediaRecord:
    """业务记录保留各自的文件名，原件按内容复用。"""

    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(ForeignKey("media_objects.sha256"), index=True)

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
    status: Mapped[StatusValue] = mapped_column(String(16), default=Status.QUEUED)
    prompt_id: Mapped[str | None] = mapped_column(String(64))
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
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="execution_status",
        ),
    )


class Work(SoftDelete, Base):
    """从成功执行发布的作品，固定来源版本、封面和允许共享的参数。"""

    __tablename__ = "works"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
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
    """用户上传的私有输入素材，可通过 `TaskAsset` 绑定到任务的节点输入。"""

    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    __table_args__ = (Index("ix_assets_created", "created_at", "id"),)


class TaskAsset(Base):
    __tablename__ = "task_assets"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    input_name: Mapped[str] = mapped_column(String(256), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
