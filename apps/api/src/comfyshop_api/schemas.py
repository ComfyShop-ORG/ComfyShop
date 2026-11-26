"""API 的输入输出契约。客户端类型由这里的 OpenAPI 定义生成。"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, get_args
from uuid import UUID

from comfyshop_worker_protocol import TaskStage, WorkerProtocolVersion
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from comfyshop_api.core.categories import WorkflowCategory
from comfyshop_api.core.i18n import msg
from comfyshop_api.core.languages import LANGUAGES
from comfyshop_api.models import ComfyStatus, StartupIssue, Status, TeamRole

MAX_TEXT_INPUT_LENGTH = 65_536
MAX_OFFICIAL_TEXT_INPUT_LENGTH = 4 * 1024 * 1024

if TYPE_CHECKING:
    from comfyshop_api.models import Team, User


class DTO(BaseModel):
    # API 使用 camelCase，Python 内部使用 snake_case，额外字段触发校验错误。
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )


class WebPushRead(DTO):
    public_key: str | None
    enabled: bool


class WebPushWrite(DTO):
    endpoint: str = Field(min_length=1, max_length=2048)
    p256dh: str = Field(alias="p256dh", pattern=r"^[A-Za-z0-9_-]{87}$")
    auth: str = Field(pattern=r"^[A-Za-z0-9_-]{22}$")
    expires_at: int | None = Field(default=None, ge=0, le=253402300799999)


class Credentials(DTO):
    username: str = Field(min_length=2, max_length=32)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = unicodedata.normalize("NFKC", value).strip()
        if not re.fullmatch(r"[\w-]{2,32}", value, re.UNICODE):
            raise ValueError(msg("media.useLettersChineseCharactersDigitsUnderscores"))
        return value


Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]


def _email(value: str | None) -> str | None:
    """去掉首尾空白并检查基本格式。空字符串表示不设邮箱。"""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError(msg("media.invalidEmailAddress"))
    return value


class PasswordChange(DTO):
    current_password: SecretStr = Field(max_length=128)
    new_password: Password


class EmailUpdate(DTO):
    # 空值解除绑定。新邮箱要在确认邮件里点击链接后才生效。修改找回方式需要再次输入密码。
    email: str | None = Field(default=None, max_length=254)
    password: SecretStr = Field(max_length=128)

    _normalize = field_validator("email")(_email)


class Registration(Credentials):
    # 注册时可以顺便填写邮箱（用于找回密码），确认邮件里的链接后生效；留空则以后在账号设置里绑定。
    email: str | None = Field(default=None, max_length=254)

    _normalize_email = field_validator("email")(_email)


class PasswordResetRequest(DTO):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def trimmed(cls, value: str) -> str:
        # 频率限制和查找都使用去掉首尾空白的邮箱，加空格不能绕过同一邮箱的限制。
        return value.strip()


class PasswordResetConfirm(DTO):
    token: str = Field(min_length=1, max_length=128)
    password: Password


class EmailConfirm(DTO):
    token: str = Field(min_length=1, max_length=128)


class AccountDelete(DTO):
    password: SecretStr = Field(max_length=128)


class NicknameUpdate(DTO):
    nickname: str | None = Field(max_length=32)

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = unicodedata.normalize("NFC", value).strip()
        if any(unicodedata.category(char) in {"Cc", "Cs", "Zl", "Zp"} for char in value):
            raise ValueError(msg("media.useASingleLineForThe"))
        return value or None


class AuthorRead(DTO):
    username: str
    nickname: str | None = None
    avatar_url: str | None = None

    @classmethod
    def from_user(cls, user: "User") -> Self:
        profile = cls.model_validate(user)
        if user.avatar_digest is not None:
            profile.avatar_url = f"/api/v1/authors/{user.id}/avatar/{user.avatar_digest}"
        return profile


class PublicTeamIdentity(DTO):
    id: str
    name: str
    avatar_url: str | None = None


class UserRead(AuthorRead):
    id: str
    email: str | None = None
    # 已填写、还在等邮件确认的邮箱。确认前找回密码仍使用 `email`。
    pending_email: str | None = None


class SessionRead(DTO):
    user: UserRead | None
    csrf_token: str | None


class ThumbnailRead(DTO):
    src: str
    sizes: list[int] = Field(description="缩略图长边像素档位，从小到大")


InputMediaKind = Literal["image", "video", "audio", "3d"]
MediaKind = Literal[InputMediaKind, "text"]
MEDIA_INPUT_KINDS = get_args(InputMediaKind)


class MediaRead(DTO):
    src: str
    width: int | None
    height: int | None
    kind: MediaKind = "image"
    video: str | None = None
    thumbnail: ThumbnailRead | None = None
    video_preview: ThumbnailRead | None = None
    filename: str | None = None
    duration_ms: int | None = None


class CoverImageRead(MediaRead):
    """独立封面只提供经过对应结果或作品授权的缩略图地址。"""

    sha256: str


class WorkflowCreate(DTO):
    name: str = Field(min_length=1, max_length=120)
    category: WorkflowCategory = WorkflowCategory.IMAGE
    graph: dict[str, Any]

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(msg("workflow.enterAName"))
        return value.strip()


class WorkflowUpdate(DTO):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: WorkflowCategory | None = None
    # 不传表示不修改，空字符串清除简介。
    description: str | None = Field(default=None, max_length=2000)
    graph: dict[str, Any] | None = None


class WorkerRoute(DTO):
    kind: str
    connection: Literal["machine", "account", "platform"]
    label: str
    scope: str | None = None
    tracks_takeover: bool = False
    imports_reference: bool = False


class WorkerType(WorkerRoute):
    sites: dict[str, str] = Field(default_factory=dict)


class ConnectionWrite(DTO):
    kind: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    scope: str = Field(min_length=1, max_length=80)
    api_key: SecretStr = Field(min_length=1, max_length=512)


class ReferenceImport(DTO):
    machine_id: str
    reference: str = Field(min_length=1, max_length=2048)
    name: str | None = Field(default=None, max_length=120)
    category: WorkflowCategory = WorkflowCategory.IMAGE


class WorkflowRead(DTO):
    id: str
    name: str
    author: str
    author_profile: AuthorRead
    owner: str
    team_id: str | None = None
    public_team: PublicTeamIdentity | None = None
    category: WorkflowCategory
    published: bool
    version_id: str
    version: int
    worker: WorkerRoute
    format: Literal["api", "ui", "service", "remote"]
    graph_hash: str
    requirements: list[str]
    media: MediaRead | None = None
    # 作者指定为封面的作品。为空时封面取作者最近公开的作品。
    cover_work_id: str | None = None
    updated: int
    description: str = ""
    # 收藏这个工作流的账号数。
    popularity: int = 0
    # 所有账号用这个工作流成功完成的任务数。
    runs: int = 0


class WorkflowPage(DTO):
    items: list[WorkflowRead]
    next_cursor: str | None


class WorkflowVersionRead(DTO):
    id: str
    number: int
    published: bool


class WorkflowVersions(DTO):
    current_version_id: str
    items: list[WorkflowVersionRead]


class GraphRead(DTO):
    version_id: str
    graph: dict[str, Any]


IdempotencyKey = Annotated[str, Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]
ExecutionIndex = Annotated[int, Field(ge=0, le=31)]


class GenerationInputs(DTO):
    workflow_id: str
    version_id: str
    input_values: dict[str, "InputValue"] = Field(max_length=2000)
    input_schema_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_execution_id: str | None = None
    source_work_id: str | None = None


class CostEstimate(DTO):
    unit_price: Decimal = Field(ge=0, max_digits=30, decimal_places=20, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    estimated: bool

    @field_serializer("unit_price")
    def serialize_price(self, price: Decimal) -> str:
        return format(price, "f") if price else "0"


class TaskCreate(GenerationInputs):
    execution_count: int = Field(default=1, ge=1, le=32)
    # 同账号重试同一次提交时复用此键，服务端会核对请求参数。
    idempotency_key: IdempotencyKey
    machine_id: str | None = None
    project_id: UUID | None = None


class TaskMachineChange(DTO):
    machine_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


class TaskRetryRequest(TaskMachineChange):
    execution_indices: list[ExecutionIndex] = Field(min_length=1, max_length=32)
    idempotency_key: IdempotencyKey


class ServiceRetryRequest(DTO):
    service: Literal[True]
    execution_indices: list[ExecutionIndex] = Field(min_length=1, max_length=32)
    idempotency_key: IdempotencyKey


class TaskRead(DTO):
    id: str
    owner: str
    workflow_id: str
    version_id: str
    workflow_name: str
    execution_count: int
    status: Status
    progress: int
    machine_id: str | None
    machine_name: str | None
    worker: WorkerRoute
    cloud_cancel: Literal["not_submitted", "accepted", "unconfirmed"] | None = None
    stage: str
    error: str | None
    prompt_id: str | None
    started: int
    updated: int
    input_values: dict[str, "InputValue"]
    source_execution_id: str | None = None
    source_work_id: str | None = None
    project_id: str | None = None
    # 任务列表里代表这次提交的成品，取最早一次有成品的执行。还没有成品时为空。
    media: MediaRead | None = None


class TaskPage(DTO):
    items: list[TaskRead]
    next_cursor: str | None


class ActiveTaskRead(DTO):
    id: str
    status: Literal[Status.QUEUED, Status.RUNNING]
    progress: int
    stage: str
    updated: int


class TaskActivity(DTO):
    active_tasks: list[ActiveTaskRead]
    completed_executions: int


class ExecutionState(DTO):
    id: str
    index: int
    status: Status
    recovery: Literal["pending", "unverified", "uploading", "rerunnable", "scheduled"] | None = None
    retry_task_id: str | None = None


# 没有已知等待原因时用 None。
TaskWaitReason = Literal[
    "machine_unassigned",
    "machine_paused",
    "machine_offline",
    "machine_busy",
    "machine_updating",
    "comfy_unreachable",
    "comfy_busy",
    "official_no_recent_poll",
    "official_busy",
    "official_waiting",
    "service_waiting",
]


class TakeoverWaitRead(DTO):
    number: int
    started_at: int
    ended_at: int | None
    duration_ms: int
    outcome: Literal["waiting", "resumed", "ended"]


class TakeoverHistoryRead(DTO):
    waits: list[TakeoverWaitRead]


class TaskProgressRead(DTO):
    status: Status
    progress: int
    stage: str
    error: str | None
    updated: int
    machine_name: str | None
    wait_reason: TaskWaitReason | None
    machine_id: str | None = None
    queue_ahead: int | None = None
    official_takeover: Literal["waiting", "resumed"] | None = None
    takeover_history: TakeoverHistoryRead | None = None
    executions: list[ExecutionState]


class WorkspaceRead(DTO):
    favorite_ids: list[str]
    can_import_official_workflows: bool
    can_manage_official_import_grants: bool


class TeamName(DTO):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TeamRead(TeamName):
    id: str
    role: TeamRole
    avatar_url: str | None = None
    profile_public: bool

    @classmethod
    def from_team(cls, team: "Team", role: TeamRole) -> Self:
        return cls(
            id=team.id,
            name=team.name,
            role=role,
            avatar_url=team_avatar_url(team),
            profile_public=team.profile_public,
        )


def team_avatar_url(team: "Team") -> str | None:
    return f"/api/v1/teams/{team.id}/avatar/{team.avatar_digest}" if team.avatar_digest else None


class PublicTeamRead(PublicTeamIdentity):
    has_workflows: bool


class TeamProfileVisibility(DTO):
    public: StrictBool


class TeamPage(DTO):
    items: list[TeamRead]
    next_cursor: str | None


class ProjectCreate(DTO):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=480)] = ""


class ProjectRead(ProjectCreate):
    id: str
    created: int
    archived_at: int | None


class ProjectListItem(ProjectRead):
    cover: MediaRead | None


class ProjectPage(DTO):
    items: list[ProjectListItem]
    next_cursor: str | None


class ProjectArchive(DTO):
    archived: StrictBool


class TaskProjectChange(DTO):
    project_id: UUID | None


class ArchivedTeamRead(TeamName):
    id: str
    archived_at: int
    has_queued_tasks: bool


class ArchivedTeamPage(DTO):
    items: list[ArchivedTeamRead]
    next_cursor: str | None


class TeamMemberChange(DTO):
    role: Literal[TeamRole.READER, TeamRole.EDITOR, TeamRole.MANAGER]


class TeamMemberRead(AuthorRead):
    id: str
    role: TeamRole


class TeamMemberPage(DTO):
    items: list[TeamMemberRead]
    next_cursor: str | None


type TeamEventCategory = Literal[
    "team",
    "project",
    "member",
    "machine",
    "workflow",
    "favorite",
    "task",
    "execution",
    "artifact",
    "work",
    "asset",
]


class TeamEventRead(DTO):
    id: str
    action: str
    actor_name: str | None
    actor_username: str | None
    record_id: str
    target: str | None
    created: int


class TeamEventPage(DTO):
    items: list[TeamEventRead]
    next_cursor: str | None


class WorkspaceShareAccount(DTO):
    id: str
    username: str


class WorkspaceSharePage(DTO):
    items: list[WorkspaceShareAccount]
    next_cursor: str | None


class OfficialImportGrantPage(DTO):
    items: list[str]
    next_cursor: str | None


class OfficialImportGrantWrite(DTO):
    granted: StrictBool


class ErrorRead(DTO):
    detail: str


class MachineCreate(DTO):
    name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


class MachinePause(DTO):
    paused: StrictBool


class MachineReconnect(DTO):
    machine_id: str = Field(min_length=1, max_length=36)


WorkerVersion = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,5})(\.(0|[1-9][0-9]{0,5})){2}$")]
WorkerDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class WorkerRuntime(DTO):
    version: WorkerVersion
    build: WorkerDigest | None = None
    can_update: bool = False


class WorkerRelease(DTO):
    version: WorkerVersion
    build: WorkerDigest
    protocol_version: WorkerProtocolVersion
    sha256: WorkerDigest
    size: int = Field(gt=0, le=16 * 1024 * 1024)
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")


class MachineUpdate(DTO):
    id: str
    release: WorkerRelease | None = None
    status: Literal["pending", "updating", "succeeded", "failed"]
    error: str | None = None


class MachineUpdateFailure(DTO):
    id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    reason: str = Field(min_length=1, max_length=200)


class WorkerRuntimeReport(WorkerRuntime):
    failure: MachineUpdateFailure | None = None
    checking: bool = False


MachineOperatingSystem = Literal["windows", "macos", "linux"]


class MachineRead(DTO):
    worker: WorkerRoute
    id: str
    name: str
    key_prefix: str
    device: str
    operating_system: MachineOperatingSystem | None = None
    online: bool
    busy: bool
    paused: bool
    revoked: bool
    last_seen: int | None
    node_count: int
    catalog_synced_at: int | None = None
    comfy_status: ComfyStatus | None = None
    startup_issue: StartupIssue | None = None
    startup_issue_at: int | None = None
    runtime: WorkerRuntime | None = None
    update: MachineUpdate | None = None
    update_available: bool = False


class MachineCurrentTask(DTO):
    id: str
    workflow_name: str
    stage: str
    progress: int


class MachineDetail(DTO):
    machine: MachineRead
    current_task: MachineCurrentTask | None
    queued_count: int


class MachineKey(DTO):
    machine: MachineRead
    api_key: str


class MachineLinkRequest(DTO):
    # 工作机上报的主机名，作为网页确认时的默认名称。
    name: str = Field(default="", max_length=80)


class MachineLinkStart(DTO):
    secret: str
    code: str
    verification_path: str
    expires_in: int
    interval: int


class MachineLinkToken(DTO):
    secret: str = Field(min_length=1, max_length=128)


class MachineLinkResult(DTO):
    status: Literal["pending", "approved"]
    api_key: str | None = None
    machine_name: str | None = None


class MachineLinkRead(DTO):
    code: str
    name: str
    status: Literal["pending", "approved", "linked"]
    requested_at: int
    expires_at: int
    # 申请来自的网络地址，以及它是否与正在查看确认页的浏览器在同一网络。地址未知或
    # 两者一个是 IPv4 一个是 IPv6 时无从比较，为空。
    source: str
    same_network: bool | None


class MachinePage(DTO):
    connection_types: list[WorkerType] = Field(default_factory=list)
    items: list[MachineRead]
    default_machine_id: str | None
    worker_release: WorkerRelease | None = None


class MachineHeartbeat(DTO):
    protocol_version: WorkerProtocolVersion
    runtime: WorkerRuntimeReport
    operating_system: MachineOperatingSystem | None
    comfy_status: ComfyStatus | None = None
    startup_issue: StartupIssue | None = None
    device: str = Field(default="", max_length=200)
    nodes: list[str] = Field(default_factory=list, max_length=30000)


class ClaimRequest(DTO):
    protocol_version: WorkerProtocolVersion
    claim_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    lease_secret: SecretStr = Field(min_length=32, max_length=128)


class ServiceClaimRequest(ClaimRequest):
    adapters: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        min_length=1, max_length=16
    )


class JobSeed(DTO):
    node_id: str
    input_name: str
    value: str = Field(pattern=r"^-?(0|[1-9][0-9]*)$")


class JobRead(DTO):
    worker_context: dict = Field(default_factory=dict)
    task: TaskRead
    graph: dict[str, Any]
    lease_expires_at: int
    assets: list["JobAsset"]
    execution_seeds: list[list[JobSeed]]
    prompt_preview_node_id: str | None = None
    recovery_window_seconds: int = Field(gt=0)
    max_artifact_bytes: int = Field(ge=1024)


class JobExecution(DTO):
    index: int
    status: Status
    prompt_id: str | None
    submission_pending: bool


class ServiceJobRead(JobRead):
    executions: list[JobExecution]
    event_sequence: int


class WorkerEvent(DTO):
    sequence: int = Field(ge=1)
    # 工作机只可上报 0–99，任务完成后由平台写入 100。
    progress: int = Field(ge=0, le=99)
    stage: TaskStage
    prompt_id: str | None = Field(default=None, max_length=64)
    execution_index: int = Field(ge=0, le=31)


class WorkerFailure(DTO):
    error: str = Field(min_length=1, max_length=2000)
    retryable_execution_index: ExecutionIndex | None = None


class OfficialExecutionFailure(DTO):
    error: str = Field(min_length=1, max_length=2000)
    retryable: bool


class WorkerRecovery(DTO):
    prompt_id: str = Field(min_length=1, max_length=64)
    outcome: Literal["outputs", "missing"]


class WorkerRecoveryRead(DTO):
    action: Literal["upload", "done"]
    client_ids: list[str] = Field(default_factory=list)


class ArtifactRead(DTO):
    id: str
    task_id: str
    workflow_id: str
    workflow_name: str
    filename: str
    sha256: str
    size: int
    content_type: str
    media: MediaRead
    execution_id: str
    output_node_id: str
    output_node_title: str
    output_slot: str
    output_index: int
    created: int


class ArtifactPage(DTO):
    items: list[ArtifactRead]
    next_cursor: str | None


class ExecutionRead(DTO):
    id: str
    task_id: str
    task_owner_id: str | None = None
    project_id: str | None = None
    workflow_id: str
    version_id: str
    workflow_name: str
    index: int
    status: Status
    prompt_id: str | None
    input_values: dict[str, "InputValue"]
    effective_prompt: str | None = None
    prompt_expanded: bool | None = None
    cover_artifact_id: str | None
    # 封面视频所选画面的时间点，单位毫秒。用首帧或封面是图片时为空。
    cover_frame_ms: int | None = None
    cover_image: CoverImageRead | None = None
    media: MediaRead | None
    image_count: int
    video_count: int
    audio_count: int
    model_count: int
    text_count: int
    artifact_count: int
    created: int


class ExecutionPage(DTO):
    items: list[ExecutionRead]
    next_cursor: str | None


class ExecutionStart(DTO):
    prompt_id: str = Field(min_length=1, max_length=64)


class ExecutionComplete(DTO):
    client_ids: list[str] = Field(min_length=1, max_length=1024)
    effective_prompt: str | None = Field(
        default=None, min_length=1, max_length=MAX_TEXT_INPUT_LENGTH
    )


# 视频封面可选的最晚时间点：一天。实际上限是视频自己的长度，设置时核对。
MAX_COVER_FRAME_MS = 24 * 60 * 60 * 1000
CoverFrame = Annotated[int | None, Field(ge=0, le=MAX_COVER_FRAME_MS)]


class CoverUpdate(DTO):
    # 使用一个成品或一张私有图片。两者都为空时恢复默认。
    artifact_id: str | None = None
    asset_id: str | None = None
    # 封面是视频时取哪一刻的画面，单位毫秒。不传或传 0 用首帧，只有视频可以指定。
    frame_ms: CoverFrame = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.artifact_id is not None and self.asset_id is not None:
            raise ValueError(msg("media.selectASingleCoverSource"))
        if self.frame_ms and self.artifact_id is None:
            raise ValueError(msg("media.chooseACoverOutputBeforeSelecting"))
        return self


class WorkflowCoverUpdate(DTO):
    # 指定公开作品或自己的图片。两者为空时取消作品指定，保留之前上传的图片。
    work_id: str | None = None
    asset_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.work_id is not None and self.asset_id is not None:
            raise ValueError(msg("media.selectASingleCoverSource"))
        return self


class WorkCreate(DTO):
    id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    execution_id: str
    title: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")
    artifact_ids: list[str] = Field(min_length=1, max_length=1024)
    # 同次执行中未选中公开的图片也可以只用作展示封面。
    cover_artifact_id: str | None = None
    # 封面是视频时取哪一刻的画面，单位毫秒。不传或传 0 用首帧，只有视频可以指定。
    cover_frame_ms: CoverFrame = None
    cover_asset_id: str | None = None
    # 确认发布时预览的结果封面。仅接受该次执行仍在使用的图片。
    execution_cover_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    share_parameters: bool = False
    # 完整输入包括标量参数和本次执行使用的参考素材。
    share_assets: bool = False
    description: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_cover_source(self) -> Self:
        if self.cover_asset_id is not None and self.execution_cover_sha256 is not None:
            raise ValueError(msg("media.selectASingleSeparateCoverSource"))
        if self.cover_frame_ms and self.cover_artifact_id is None:
            raise ValueError(msg("media.chooseACoverOutputBeforeSelecting"))
        return self


class WorkRead(DTO):
    id: str
    title: str
    author: str
    author_profile: AuthorRead
    owner: str
    team_id: str | None = None
    public_team: PublicTeamIdentity | None = None
    workflow_id: str
    workflow_name: str
    category: WorkflowCategory
    version_id: str
    execution_id: str
    cover_artifact_id: str
    cover_frame_ms: int | None = None
    cover_image: CoverImageRead | None = None
    media: MediaRead
    asset_count: int
    published: bool
    input_values: dict[str, "InputValue"]
    created: int
    description: str = ""


class WorkPage(DTO):
    items: list[WorkRead]
    next_cursor: str | None


class ReplayRead(DTO):
    workflow: WorkflowRead
    source_execution_id: str | None = None
    source_work_id: str | None = None
    project_id: str | None = None


class AssetReference(DTO):
    asset_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


ScalarInput = StrictStr | StrictBool | StrictInt | StrictFloat
InputValue = ScalarInput | AssetReference | None


class WorkflowInputContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_team: UUID | None = None
    version_id: str | None = None
    execution_id: str | None = None
    work_id: str | None = None


class WorkflowInputQuery(WorkflowInputContext):
    machine_id: str


class NodeInput(DTO):
    # string 文本，integer 整数，number 数值，boolean 开关，choice 枚举，image/video 素材。
    kind: Literal["string", "integer", "number", "boolean", "choice", InputMediaKind]
    label: str = Field(default="", max_length=160)
    choices: list[StrictStr | StrictInt | StrictFloat | StrictBool] = Field(
        default_factory=list, max_length=5000
    )
    minimum: str | None = Field(default=None, max_length=80)
    maximum: str | None = Field(default=None, max_length=80)
    step: str | None = Field(default=None, max_length=80)
    multiline: bool = False

    @field_validator("minimum", "maximum", "step")
    @classmethod
    def finite_bound(cls, value: str | None):
        if value is not None:
            try:
                if not Decimal(value).is_finite():
                    raise ValueError(msg("media.invalidInputRange"))
            except InvalidOperation:
                raise ValueError(msg("media.invalidInputRange")) from None
        return value


class NodeCatalog(DTO):
    inputs: dict[str, NodeInput] = Field(default_factory=dict, max_length=500)
    output_node: bool = False
    title: str = Field(default="", max_length=160)


class MachineCatalog(DTO):
    nodes: dict[str, NodeCatalog] = Field(max_length=30000)


class WorkflowInput(NodeInput):
    id: str
    node_id: str
    input_name: str
    node_title: str
    default: InputValue = None
    primary: bool = False
    # 字段是否有中文名称。没有名称的冷门参数默认不显示，由作者决定是否放出。
    named: bool = True
    integer_as_string: bool = False
    optional: bool = False
    additional_asset_kinds: list[InputMediaKind] | None = Field(
        default=None, max_length=3, exclude_if=lambda value: not value
    )
    accepted_content_types: list[str] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    max_length: int | None = Field(
        default=None,
        gt=0,
        le=MAX_OFFICIAL_TEXT_INPUT_LENGTH,
        exclude_if=lambda value: value is None,
    )


OFFICIAL_INPUT_NAME = r"[a-zA-Z][a-zA-Z0-9_]{0,63}"


class OfficialInput(NodeInput):
    name: str = Field(pattern=rf"^{OFFICIAL_INPUT_NAME}$")
    default: ScalarInput | None = None
    primary: bool = True
    optional: bool = False
    additional_asset_kinds: list[InputMediaKind] | None = Field(
        default=None, max_length=3, exclude_if=lambda value: not value
    )
    max_length: int | None = Field(
        default=None,
        gt=0,
        le=MAX_OFFICIAL_TEXT_INPUT_LENGTH,
        exclude_if=lambda value: value is None,
    )

    choice_labels: dict[str, Annotated[str, Field(min_length=1, max_length=160)]] | None = Field(
        default=None, max_length=5000, exclude_if=lambda value: not value
    )


class OfficialExecution(DTO):
    adapter: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    output_kind: MediaKind
    additional_output_kinds: list[MediaKind] = Field(
        default_factory=list, max_length=len(MEDIA_INPUT_KINDS)
    )
    config: dict[str, Any]


ParameterControl = Literal["text", "textarea", "slider", "checkbox", "radio"]


class ParameterSlider(DTO):
    """对齐到步长的滑块范围，以缩放后的安全整数表示。"""

    minimum: int
    maximum: int
    step: int
    scale: int


class WorkflowParameterControls(DTO):
    options: list[ParameterControl]
    slider: ParameterSlider | None = None


class WorkflowOutpaint(DTO):
    """扩图预览写回的四个边距字段 ID。"""

    left: str
    top: str
    right: str
    bottom: str


class WorkflowCropBox(DTO):
    """可编辑裁剪框的原图像素坐标字段。"""

    x: str
    y: str
    width: str
    height: str


class WorkflowPlacementLayer(DTO):
    """图层按工作流的合成顺序排列，变换引用图中的原有字段。"""

    image: str
    x: str
    y: str
    resize: str
    scale: str | None = None
    rotation: str | None = None
    alpha: bool


class WorkflowMask(DTO):
    """独立遮罩有通道字段，原图自带的遮罩可用同尺寸 PNG 覆盖。"""

    field_id: str
    channel_field_id: str | None = Field(default=None, exclude_if=lambda value: value is None)


class WorkflowParameterPresentation(DTO):
    choice_labels: dict[str, str] = Field(default_factory=dict)
    guidance: str | None = None
    outpaint: WorkflowOutpaint | None = Field(default=None, exclude_if=lambda value: value is None)
    layers: list[WorkflowPlacementLayer] = Field(
        default_factory=list, exclude_if=lambda value: not value
    )
    crop: WorkflowCropBox | None = Field(default=None, exclude_if=lambda value: value is None)
    mask: WorkflowMask | None = Field(default=None, exclude_if=lambda value: value is None)


class WorkflowParameterDisplay(DTO):
    """单个参数的展示与默认值配置。数组中的位置决定区内顺序。"""

    field_id: str = Field(pattern=rf"^(?:[a-f0-9]{{64}}|{OFFICIAL_INPUT_NAME})$")
    section: Literal["default", "advanced", "hidden"]
    display_name: str | None = Field(default=None, max_length=160)
    help: str | None = Field(default=None, max_length=500)
    control: ParameterControl | None = None
    default_value: ScalarInput | None = None

    @field_validator("display_name", "help")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class FieldWorkflow(DTO):
    fields: list[OfficialInput] = Field(min_length=1, max_length=100)
    parameter_layout: list[WorkflowParameterDisplay] = Field(default_factory=list, max_length=100)
    execution: OfficialExecution


class OfficialFieldTranslation(DTO):
    label: str | None = Field(default=None, max_length=160)
    choice_labels: dict[str, Annotated[str, Field(min_length=1, max_length=160)]] | None = Field(
        default=None, max_length=5000
    )


class OfficialParameterTranslation(DTO):
    display_name: str | None = Field(default=None, max_length=160)
    help: str | None = Field(default=None, max_length=500)


class OfficialTranslation(DTO):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    fields: dict[str, OfficialFieldTranslation] = Field(default_factory=dict, max_length=100)
    parameter_layout: dict[str, OfficialParameterTranslation] = Field(
        default_factory=dict, max_length=100
    )


class ServiceManifest(FieldWorkflow):
    format: Literal["service"]
    worker_kind: str
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,119}$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: WorkflowCategory
    translations: dict[str, OfficialTranslation] = Field(
        default_factory=dict, max_length=len(LANGUAGES)
    )

    @field_validator("translations")
    @classmethod
    def supported_translations(
        cls, value: dict[str, OfficialTranslation]
    ) -> dict[str, OfficialTranslation]:
        if value.keys() - LANGUAGES.keys():
            raise ValueError(msg("workflow.invalidData"))
        return value

    @property
    def source_identity(self) -> str:
        return f"{self.worker_kind}:platform:{self.key}"


class WorkflowParameterLayoutUpdate(DTO):
    machine_id: str | None = None
    parameter_layout: list[WorkflowParameterDisplay]


class WorkflowRatioSize(DTO):
    kind: Literal["ratio"] = "ratio"
    ratio_field_id: str
    megapixels_field_id: str
    multiple_field_id: str
    round_to: int | None = None
    latent_multiple: int | None = None
    model_multiple: int | None = None
    prompt_field_id: str | None = None


class WorkflowAutomaticSize(DTO):
    kind: Literal["automatic"] = "automatic"
    width_field_id: str
    height_field_id: str
    uses_reference: bool


class WorkflowReferenceFrame(DTO):
    image_field_id: str
    time_field_id: str | None = None


class WorkflowReferenceTimeline(DTO):
    duration_field_id: str
    frames_per_second: int = 24
    minimum_frames: int = 5
    frame_step: int = 17
    frames: list[WorkflowReferenceFrame]


class WorkflowCropRegion(DTO):
    label: str
    x: int
    y: int
    width: int
    height: int


class InpaintTarget(DTO):
    workflow_id: str
    scope: Literal["mine", "public"]
    version_id: str
    machine_id: str
    field_id: str
    label: str
    mask: WorkflowMask


class WorkflowFormData(DTO):
    catalog_limited: bool = False
    version_id: str
    schema_hash: str
    fields: list[WorkflowInput]
    issues: list[str] = Field(default_factory=list)
    parameter_layout: list[WorkflowParameterDisplay] = Field(default_factory=list)
    parameter_controls: dict[str, WorkflowParameterControls] = Field(default_factory=dict)
    parameter_presentation: dict[str, WorkflowParameterPresentation] = Field(default_factory=dict)
    output_sizes: list[WorkflowRatioSize | WorkflowAutomaticSize] = Field(default_factory=list)
    reference_timelines: list[WorkflowReferenceTimeline] = Field(default_factory=list)
    image_crops: dict[str, list[WorkflowCropRegion]] = Field(default_factory=dict)
    original_defaults: dict[str, ScalarInput] = Field(default_factory=dict)
    shared_assets: list["AssetRead"] = Field(default_factory=list)
    max_asset_bytes: int | None = None
    cost_estimate: bool | None = None


class WorkflowForm(WorkflowFormData):
    machine_id: str


class AssetRead(DTO):
    id: str
    filename: str
    sha256: str
    size: int
    content_type: str
    media: MediaRead
    saved_at: int | None = None


class AssetPage(DTO):
    items: list[AssetRead]
    next_cursor: str | None


class AssetUsage(DTO):
    used_bytes: int
    remaining_bytes: int
    limit_bytes: int


class RecordedInput(DTO):
    id: str
    label: str
    node_id: str
    node_title: str
    input_name: str


class OutputComparison(DTO):
    """原图在成品坐标系中的位置，使用放大前的画布像素。"""

    asset_id: str
    width: int
    height: int
    x: int = 0
    y: int = 0
    uniform_upscale: bool = False


class TaskInputsRead(DTO):
    version: int
    fields: list[RecordedInput]
    assets: list[AssetRead]
    comparisons: dict[str, OutputComparison] = Field(
        default_factory=dict, exclude_if=lambda value: not value
    )


class JobAsset(AssetRead):
    node_id: str
    input_name: str


TaskCreate.model_rebuild()
TaskRead.model_rebuild()
JobRead.model_rebuild()
ExecutionRead.model_rebuild()
WorkRead.model_rebuild()
