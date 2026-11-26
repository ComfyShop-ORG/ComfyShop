"""工作机注册入口。工作流、连接选择、任务分派与成品校验共用此目录。"""

from comfyshop_runninghub_worker.provider import definition as runninghub
from comfyshop_worker_protocol.definition import OFFICIAL, PERSONAL, WorkerDefinition
from fastapi import HTTPException

from comfyshop_api.core.i18n import msg
from comfyshop_api.schemas import WorkerRoute, WorkerType

WORKERS = {worker.kind: worker for worker in (PERSONAL, OFFICIAL, runninghub)}


def worker_type(kind: str) -> WorkerDefinition:
    if kind not in WORKERS:
        raise HTTPException(422, msg("connection.workerTypeUnavailable"))
    return WORKERS[kind]


def route(kind: str, scope: str | None = None) -> WorkerRoute:
    w = worker_type(kind)
    return WorkerRoute(
        kind=w.kind,
        label=w.label,
        connection=w.connection,
        scope=scope,
        tracks_takeover=w.tracks_takeover,
        imports_reference=w.load_reference is not None,
    )


def connection_types() -> list[WorkerType]:
    return [
        WorkerType(**route(w.kind).model_dump(), sites=w.sites)
        for w in WORKERS.values()
        if w.connection == "account"
    ]


def personal_worker_kinds() -> list[str]:
    return [w.kind for w in WORKERS.values() if not w.service]
