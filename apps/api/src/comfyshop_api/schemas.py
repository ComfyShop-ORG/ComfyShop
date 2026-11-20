"""API 的输入输出契约。客户端类型由这里的 OpenAPI 定义生成。"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    StrictInt,
    StrictFloat,
    StrictStr,
    field_validator,
)
from pydantic.alias_generators import to_camel


class DTO(BaseModel):
    # API 使用 camelCase，Python 内部使用 snake_case，额外字段触发校验错误。
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )


class Credentials(DTO):
    username: str = Field(min_length=2, max_length=32)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = unicodedata.normalize("NFKC", value).strip()
        if not re.fullmatch(r"[\w-]{2,32}", value, re.UNICODE):
            raise ValueError("账号需为 2–32 位字母、汉字、数字、下划线或连字符")
        return value


Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]


def _email(value: str | None) -> str | None:
    """去掉首尾空白并检查基本格式。空字符串表示不设邮箱。"""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("邮箱格式无效")
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


class UserRead(DTO):
    id: str
    username: str
    email: str | None = None
    # 已填写、还在等邮件确认的邮箱。确认前找回密码仍使用 `email`。
    pending_email: str | None = None


class SessionRead(DTO):
    user: UserRead | None
    csrf_token: str | None


class ThumbnailRead(DTO):
    src: str
    sizes: list[int] = Field(description="缩略图长边像素档位，从小到大")


class MediaRead(DTO):
    src: str
    width: int
    height: int
    video: str | None = None
    thumbnail: ThumbnailRead | None = None
    video_preview: ThumbnailRead | None = None


# 分类值分别为 image（图像）、video（视频）、tool（工具）。
class WorkflowCreate(DTO):
    name: str = Field(min_length=1, max_length=120)
    category: Literal["image", "video", "tool"] = "image"
    graph: dict[str, Any]

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("名称不能为空")
        return value.strip()


class WorkflowUpdate(DTO):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: Literal["image", "video", "tool"] | None = None
    # 不传表示不修改，空字符串清除简介。
    description: str | None = Field(default=None, max_length=2000)
    graph: dict[str, Any] | None = None


class WorkflowRead(DTO):
    id: str
    name: str
    author: str
    owner: str
    category: Literal["image", "video", "tool"]
    published: bool
    version_id: str
    version: int
    format: Literal["api", "ui"]
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


class GraphRead(DTO):
    version_id: str
    graph: dict[str, Any]


class TaskCreate(DTO):
    workflow_id: str
    version_id: str
    execution_count: int = Field(default=1, ge=1, le=32)
    # 同账号重试同一次提交时复用此键，服务端会核对请求参数。
    idempotency_key: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    machine_id: str | None = None
    input_values: dict[str, "InputValue"] = Field(max_length=2000)
    input_schema_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_execution_id: str | None = None
    source_work_id: str | None = None


# queued 等待领取，running 已领取并执行或回传。
# succeeded 已确认成品清单，failed 执行或租约失败，cancelled 排队时取消。
TaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class TaskRead(DTO):
    id: str
    workflow_id: str
    version_id: str
    workflow_name: str
    execution_count: int
    status: TaskStatus
    progress: int
    machine_id: str | None
    stage: str
    error: str | None
    prompt_id: str | None
    started: int
    updated: int
    input_values: dict[str, "InputValue"]
    source_execution_id: str | None = None
    source_work_id: str | None = None
    # 任务列表里代表这次提交的成品，取最早一次有成品的执行。还没有成品时为空。
    media: MediaRead | None = None


class TaskPage(DTO):
    items: list[TaskRead]
    next_cursor: str | None


class ActiveTaskRead(DTO):
    id: str
    status: Literal["queued", "running"]
    progress: int
    stage: str
    updated: int


class TaskActivity(DTO):
    active_tasks: list[ActiveTaskRead]
    completed_executions: int


class ExecutionState(DTO):
    id: str
    index: int
    status: TaskStatus


# 排队原因分别为未分配工作机、工作机离线或工作机忙碌。没有已知等待原因时用 None。
TaskWaitReason = Literal["machine_unassigned", "machine_offline", "machine_busy"]


class TaskProgressRead(DTO):
    status: TaskStatus
    progress: int
    stage: str
    error: str | None
    updated: int
    machine_name: str | None
    wait_reason: TaskWaitReason | None
    executions: list[ExecutionState]


class WorkspaceRead(DTO):
    favorite_ids: list[str]


class ErrorRead(DTO):
    detail: str


class MachineCreate(DTO):
    name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


class MachineRead(DTO):
    id: str
    name: str
    key_prefix: str
    device: str
    online: bool
    busy: bool
    revoked: bool
    last_seen: int | None
    node_count: int


class MachineKey(DTO):
    machine: MachineRead
    api_key: str


class MachineLinkRequest(DTO):
    # 工作机上报的主机名，作为网页确认时的默认名称。
    name: str = Field(default="", max_length=80)


class MachineLinkStart(DTO):
    secret: str
    code: str
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
    requested_at: int
    expires_at: int
    # 申请来自的网络地址，以及它是否与正在查看确认页的浏览器在同一网络。地址未知或
    # 两者一个是 IPv4 一个是 IPv6 时无从比较，为空。
    source: str
    same_network: bool | None


class MachinePage(DTO):
    items: list[MachineRead]
    default_machine_id: str | None


class MachineHeartbeat(DTO):
    # 心跳和领取使用协议 3，要求冻结种子、执行序号和成品来源完整。
    protocol_version: Literal[3]
    device: str = Field(default="", max_length=200)
    nodes: list[str] = Field(default_factory=list, max_length=30000)


class ClaimRequest(DTO):
    protocol_version: Literal[3]
    claim_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    lease_secret: SecretStr = Field(min_length=32, max_length=128)


class JobSeed(DTO):
    node_id: str
    input_name: str
    value: str = Field(pattern=r"^-?(0|[1-9][0-9]*)$")


class JobRead(DTO):
    task: TaskRead
    graph: dict[str, Any]
    lease_expires_at: int
    assets: list["JobAsset"]
    execution_seeds: list[list[JobSeed]]


class WorkerEvent(DTO):
    sequence: int = Field(ge=1)
    # 工作机只可上报 0–99，任务完成后由平台写入 100。
    progress: int = Field(ge=0, le=99)
    # preflight 检查依赖，executing 执行工作流，uploading 回传成品。
    stage: Literal["preflight", "executing", "uploading"]
    prompt_id: str | None = Field(default=None, max_length=64)
    execution_index: int = Field(ge=0, le=31)


class WorkerFailure(DTO):
    error: str = Field(min_length=1, max_length=2000)


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
    workflow_id: str
    version_id: str
    workflow_name: str
    index: int
    status: TaskStatus
    prompt_id: str | None
    input_values: dict[str, "InputValue"]
    cover_artifact_id: str | None
    # 封面视频所选画面的时间点，单位毫秒。用首帧或封面是图片时为空。
    cover_frame_ms: int | None = None
    media: MediaRead | None
    image_count: int
    video_count: int
    created: int


class ExecutionPage(DTO):
    items: list[ExecutionRead]
    next_cursor: str | None


class ExecutionStart(DTO):
    prompt_id: str = Field(min_length=1, max_length=64)


class ExecutionComplete(DTO):
    client_ids: list[str] = Field(min_length=1, max_length=1024)


# 视频封面可选的最晚时间点：一天。实际上限是视频自己的长度，设置时核对。
MAX_COVER_FRAME_MS = 24 * 60 * 60 * 1000
CoverFrame = Annotated[int | None, Field(ge=0, le=MAX_COVER_FRAME_MS)]


class ExecutionCoverUpdate(DTO):
    artifact_id: str
    # 封面是视频时取哪一刻的画面，单位毫秒。不传或传 0 用首帧，只有视频可以指定。
    frame_ms: CoverFrame = None


class WorkflowCoverUpdate(DTO):
    # 作者自己在此工作流下公开的作品。传 null 恢复为取最近公开的作品。
    work_id: str | None


class WorkCreate(DTO):
    id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    execution_id: str
    title: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")
    artifact_ids: list[str] = Field(min_length=1, max_length=1024)
    cover_artifact_id: str
    # 封面是视频时取哪一刻的画面，单位毫秒。不传或传 0 用首帧，只有视频可以指定。
    cover_frame_ms: CoverFrame = None
    share_parameters: bool = False
    description: str = Field(default="", max_length=1000)


class WorkRead(DTO):
    id: str
    title: str
    author: str
    owner: str
    workflow_id: str
    workflow_name: str
    version_id: str
    execution_id: str
    cover_artifact_id: str
    cover_frame_ms: int | None = None
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


class AssetReference(DTO):
    asset_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


ScalarInput = StrictStr | StrictBool | StrictInt | StrictFloat
InputValue = ScalarInput | AssetReference | None


class WorkflowInputQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str
    version_id: str | None = None
    execution_id: str | None = None
    work_id: str | None = None


class NodeInput(DTO):
    # string 文本，integer 整数，number 数值，boolean 开关，choice 枚举，image/video 素材。
    kind: Literal["string", "integer", "number", "boolean", "choice", "image", "video"]
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
                    raise ValueError("输入范围无效")
            except InvalidOperation:
                raise ValueError("输入范围无效") from None
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


class WorkflowParameterDisplay(DTO):
    """单个参数的展示与默认值配置。数组中的位置决定区内顺序。"""

    field_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    section: Literal["default", "advanced", "hidden"]
    display_name: str | None = Field(default=None, max_length=160)
    help: str | None = Field(default=None, max_length=500)
    control: ParameterControl | None = None
    default_value: ScalarInput | None = None

    @field_validator("display_name", "help")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class WorkflowParameterLayoutUpdate(DTO):
    machine_id: str
    parameter_layout: list[WorkflowParameterDisplay]


class WorkflowForm(DTO):
    version_id: str
    machine_id: str
    schema_hash: str
    fields: list[WorkflowInput]
    issues: list[str] = Field(default_factory=list)
    parameter_layout: list[WorkflowParameterDisplay] = Field(default_factory=list)
    parameter_controls: dict[str, WorkflowParameterControls] = Field(default_factory=dict)
    original_defaults: dict[str, ScalarInput] = Field(default_factory=dict)


class AssetRead(DTO):
    id: str
    filename: str
    sha256: str
    size: int
    content_type: str
    media: MediaRead


class RecordedInput(DTO):
    id: str
    label: str
    node_id: str
    node_title: str
    input_name: str


class TaskInputsRead(DTO):
    version: int
    fields: list[RecordedInput]
    assets: list[AssetRead]


class JobAsset(AssetRead):
    node_id: str
    input_name: str


TaskCreate.model_rebuild()
TaskRead.model_rebuild()
JobRead.model_rebuild()
ExecutionRead.model_rebuild()
WorkRead.model_rebuild()
