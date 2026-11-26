"""A worker's connection policy, portable workflow capabilities and execution adapter."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import httpx

from . import TaskStage


@dataclass(frozen=True)
class Source:
    reference: str
    graph: dict
    catalog: dict = field(default_factory=dict)
    catalog_limited: bool = False
    # An omitted upload retains the provider's original input for these bindings.
    optional_assets: tuple[tuple[str, str], ...] = ()


class ExecutionAdapter(Protocol):
    async def prepare(self, job: dict, assets: dict[str, Path]) -> None: ...
    async def submit(self, index: int) -> str: ...
    async def poll(self, remote_id: str) -> TaskStage | list: ...
    async def download(self, item: dict, path: Path, index: int) -> tuple[str, str]: ...


class SubmissionRejected(ValueError):
    """The provider definitively declined this request before creating a billable task."""


@dataclass(frozen=True)
class WorkerDefinition:
    kind: str
    label: str
    connection: Literal["machine", "account", "platform"]
    form: Literal["nodes", "fields"]
    executor: Callable[[httpx.AsyncClient, dict], ExecutionAdapter] | None = None
    sites: dict[str, str] = field(default_factory=dict)
    load_reference: Callable[[str, str, str], Awaitable[Source]] | None = None
    cancel: Callable[[str, str, str], Awaitable[None]] | None = None
    output_kinds: tuple[str, ...] = ("image", "video", "audio", "3d")
    input_kinds: tuple[str, ...] = (
        "string",
        "integer",
        "number",
        "boolean",
        "choice",
        "image",
        "video",
        "audio",
        "3d",
    )
    adapters: tuple[str, ...] = ()
    tracks_takeover: bool = False
    output_node: str | None = None

    @property
    def service(self) -> bool:
        return self.connection != "machine"


PERSONAL = WorkerDefinition("comfyui", "ComfyUI", "machine", "nodes")
OFFICIAL = WorkerDefinition(
    "official",
    "ComfyShop",
    "platform",
    "fields",
    tracks_takeover=True,
    output_node="official",
    output_kinds=("image", "video", "audio", "3d", "text"),
)
