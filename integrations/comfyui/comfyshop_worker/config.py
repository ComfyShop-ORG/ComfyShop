"""读取工作机配置，并在本机保存可恢复的任务记录。"""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast
from urllib.parse import urlsplit


class MissingKey(ValueError):
    """配置里没有密钥。`server_url` 是已校验的平台地址，首次启动据此申请接入。"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        super().__init__("请配置 COMFYSHOP_API_KEY 或 COMFYSHOP_WORKER_CONFIG")


@dataclass(frozen=True)
class Config:
    """工作机的连接地址、凭据、状态路径和时间设置，两种启动方式共用。"""

    server_url: str
    comfy_url: str
    api_key: str
    state_dir: Path
    poll_seconds: float = 3
    execution_timeout_seconds: float = 3600

    @classmethod
    def load(cls):
        """从进程环境和可选 JSON 文件构造配置，环境变量优先于同名 JSON 设置。

        返回已校验的 `Config`，并确保状态目录存在。
        平台与 ComfyUI 地址须为无内嵌账号密码的 HTTP(S) URL。执行超时是以秒计的有限正数。
        字段无效时抛出 `ValueError`，地址有效但没有密钥时抛出 `MissingKey`。
        配置文件不存在时按空配置处理，读取或创建状态目录失败时传播对应的文件错误。
        """
        file = os.environ.get("COMFYSHOP_WORKER_CONFIG")
        values = json.loads(Path(file).read_text()) if file and Path(file).exists() else {}
        if not isinstance(values, dict):
            raise ValueError("工作机配置必须是 JSON 对象")

        def text_setting(variable: str, name: str, default: str) -> str:
            value = os.environ.get(variable)
            if value is None:
                value = values.get(name, default)
            if not isinstance(value, str):
                raise ValueError(f"工作机配置 {name} 必须是字符串")
            return value

        server = text_setting("COMFYSHOP_SERVER_URL", "serverUrl", "http://127.0.0.1:8688").rstrip(
            "/"
        )
        comfy = text_setting("COMFYSHOP_COMFY_URL", "comfyUrl", "http://127.0.0.1:8188").rstrip("/")
        key = text_setting("COMFYSHOP_API_KEY", "apiKey", "")
        for url in (server, comfy):
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("服务地址必须是无内嵌凭据的 HTTP(S) 地址")
        if not key:
            raise MissingKey(server)
        identity = hashlib.sha256(key.encode()).hexdigest()[:16]
        state = Path(
            text_setting(
                "COMFYSHOP_WORKER_STATE_DIR",
                "stateDir",
                str(Path.home() / ".local/share/comfyshop/worker" / identity),
            )
        )
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        timeout_value = os.environ.get("COMFYSHOP_EXECUTION_TIMEOUT_SECONDS")
        if timeout_value is None:
            timeout_value = values.get("executionTimeoutSeconds", 3600)
        if isinstance(timeout_value, bool) or not isinstance(timeout_value, (str, int, float)):
            raise ValueError("执行时间限制必须是正数秒数")
        timeout = float(timeout_value)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("执行时间限制必须是正数秒数")
        return cls(server, comfy, key, state, execution_timeout_seconds=timeout)


class RunRecord(TypedDict):
    """一次执行在本机的提交记录，重启后据此继续跟踪原 prompt。"""

    promptId: str
    clientId: str
    # prepared 等待提交，submitting 已尝试发送，submitted 继续跟踪，done 平台已确认清单。
    phase: Literal["prepared", "submitting", "submitted", "done"]
    # 首次执行的时间，执行限时从这里起计，重启后不重置。
    startedAt: NotRequired[float]


class RetryRecord(TypedDict):
    since: float
    index: int
    count: int


class WorkerState(TypedDict):
    """`active.json` 的内容。键名随文件保存，升级时需保持兼容。"""

    # 领取前生成并保存，平台据此识别同一次领取的重试。
    claimId: str
    leaseSecret: str
    # 领取响应：task、graph、assets、executionSeeds。
    job: NotRequired[dict[str, Any]]
    # 以执行序号的字符串为键。
    runs: NotRequired[dict[str, RunRecord]]
    # 下一个待执行的序号，平台确认清单后推进。
    index: NotRequired[int]
    progress: NotRequired[int]
    stage: NotRequired[str]
    promptId: NotRequired[str]
    sequence: NotRequired[int]
    # 已确定的失败原因，等待回报给平台。
    failure: NotRequired[str]
    # 正在提交最终结果，任务心跳暂停。
    finishing: NotRequired[bool]
    # 连续暂时性故障的开始时间（Unix 秒）、执行序号和次数。有进展时清除，持续超过时限
    # 后放弃该任务。
    retry: NotRequired[RetryRecord]


def write_json(path: Path, value: Any) -> None:
    """刷写同目录临时文件，再原子替换正式记录。"""
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output, ensure_ascii=False)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


class Journal:
    """单个状态目录的 `active.json`，保存领取凭据、执行位置与回传进度。"""

    def __init__(self, directory: Path):
        self.path = directory / "active.json"

    def read(self) -> WorkerState | None:
        """返回需要继续处理的记录，文件不存在时返回 `None`。无效 JSON 或非对象值抛出 `ValueError`。"""
        if not self.path.exists():
            return None
        state = json.loads(self.path.read_text())
        if not isinstance(state, dict):
            raise ValueError("工作机记录必须是 JSON 对象")
        return cast(WorkerState, state)

    def save(self, state: WorkerState) -> None:
        """先刷写同目录临时文件，再替换正式记录，使读取方只能看到完整记录。"""
        write_json(self.path, state)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
