"""工作机协议入口，接收节点目录、心跳、任务领取和执行清单。"""

from typing import Any, cast
import hashlib
import json

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import case, select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import CursorResult

from comfyshop_api.models import (
    Status,
    Asset,
    Machine,
    Task,
    TaskAsset,
    now_ms,
)
from comfyshop_api.schemas import (
    ClaimRequest,
    JobRead,
    MachineHeartbeat,
    MachineLinkRequest,
    MachineLinkResult,
    MachineLinkStart,
    MachineLinkToken,
    MachineRead,
    TaskRead,
    WorkerEvent,
    WorkerFailure,
    MachineCatalog,
    JobAsset,
    ExecutionStart,
    ExecutionComplete,
    ExecutionRead,
)
from comfyshop_api.security import Config, DB, client_address, throttle
from comfyshop_api.services.machines import (
    CurrentMachine,
    Lease,
    claim_task,
    fence,
    finish_task,
    lock_leased_task,
    machine_read,
)
from comfyshop_api.services.machine_links import (
    LINK_TTL_MS,
    POLL_SECONDS,
    redeem_link,
    request_link,
)
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.tasks import task_read
from comfyshop_api.services.executions import (
    execution_at,
    execution_reads,
    execution_seed_bindings,
    finish_execution,
    task_executions_complete,
)

router = APIRouter(prefix="/worker", tags=["worker"])


# 下载工作机启动包。包内附带平台地址，解压后直接启动即可申请接入。
@router.get("/package")
def download_package(request: Request, settings: Config) -> Response:
    source = settings.static_dir and settings.static_dir / "downloads" / "comfyshop-worker.zip"
    if not source or not source.is_file():
        raise HTTPException(404, "工作机启动包尚未生成")
    package = BytesIO(source.read_bytes())
    with ZipFile(package, "a", compression=ZIP_DEFLATED) as bundle:
        root = bundle.namelist()[0].split("/", 1)[0]
        entry = ZipInfo(f"{root}/worker.json")
        entry.external_attr = 0o100600 << 16
        bundle.writestr(
            entry,
            json.dumps(
                {
                    "serverUrl": settings.site_url(str(request.base_url)),
                    "comfyUrl": "http://127.0.0.1:8188",
                },
                indent=2,
            ),
        )
    return Response(
        package.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="comfyshop-worker.zip"'},
    )


# 首次启动的工作机申请接入，等待账号在网页确认。两个入口都不需要登录或密钥，
# 申请按来源地址限制频率，单一来源不能占满全平台的等待名额。
@router.post("/links", response_model=MachineLinkStart, status_code=201)
def start_link(body: MachineLinkRequest, request: Request, db: DB) -> MachineLinkStart:
    throttle(request, db, None, "link")
    link, secret = request_link(db, body.name, client_address(request))
    db.commit()
    return MachineLinkStart(
        secret=secret,
        code=link.code,
        expires_in=LINK_TTL_MS // 1000,
        interval=POLL_SECONDS,
    )


@router.post("/links/token", response_model=MachineLinkResult)
def redeem_machine_link(body: MachineLinkToken, db: DB) -> MachineLinkResult:
    redeemed = redeem_link(db, body.secret)
    if redeemed is None:
        return MachineLinkResult(status="pending")
    db.commit()
    api_key, name = redeemed
    return MachineLinkResult(status="approved", api_key=api_key, machine_name=name)


@router.put("/catalog", response_model=dict[str, str])
def update_catalog(body: MachineCatalog, db: DB, machine: CurrentMachine):
    nodes = {name: node.model_dump() for name, node in body.nodes.items()}
    encoded = json.dumps(nodes, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > 8 * 1024 * 1024:
        raise HTTPException(413, "节点定义过大")
    machine.catalog = nodes
    machine.catalog_hash = hashlib.sha256(encoded).hexdigest()
    db.commit()
    return {"hash": machine.catalog_hash}


@router.post("/heartbeat", response_model=MachineRead)
def heartbeat(body: MachineHeartbeat, db: DB, machine: CurrentMachine) -> MachineRead:
    machine.device = body.device
    machine.capabilities = {"nodes": body.nodes}
    machine.last_seen = now_ms()
    db.commit()
    return machine_read(machine)


def job_read(db: Session, task: Task) -> JobRead:
    assert task.lease_expires_at is not None
    assets = [
        JobAsset(
            **asset_read(asset).model_dump(), node_id=binding.node_id, input_name=binding.input_name
        )
        for binding, asset in db.execute(
            select(TaskAsset, Asset).join(Asset).where(TaskAsset.task_id == task.id)
        ).all()
    ]
    return JobRead(
        task=task_read(task),
        graph=task.input_graph,
        lease_expires_at=task.lease_expires_at,
        assets=assets,
        execution_seeds=execution_seed_bindings(db, task),
    )


# `claim_id` 与租约凭据用于重试同一次领取。机器繁忙或无可领任务时返回 JSON null。
@router.post("/claim", response_model=JobRead | None)
def claim(body: ClaimRequest, db: DB, machine: CurrentMachine, config: Config) -> JobRead | None:
    task, new_claim = claim_task(
        db,
        machine,
        body.claim_id,
        body.lease_secret.get_secret_value(),
        config.worker_lease_seconds,
    )
    if task is None:
        return None
    job = job_read(db, task)
    if new_claim:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "任务领取冲突") from None
    return job


@router.post("/tasks/{task_id}/heartbeat", response_model=TaskRead)
def task_heartbeat(
    task_id: str,
    body: WorkerEvent,
    db: DB,
    machine: CurrentMachine,
    config: Config,
    x_task_lease: Lease = None,
) -> TaskRead:
    task = fence(db, task_id, machine, x_task_lease, terminal=True)
    if task.status == Status.SUCCEEDED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, "任务租约已失效")
    prior_sequence = task.event_seq
    now = now_ms()
    until = now + config.worker_lease_seconds * 1000
    values: dict[str, Any] = {"lease_expires_at": until, "updated_at": now}
    # 已验证的旧心跳仍可续期。进度、阶段和 prompt 只接受递增的事件序号。
    newer = Task.event_seq < body.sequence
    values.update(
        event_seq=case((newer, body.sequence), else_=Task.event_seq),
        progress=case(
            (newer & (Task.progress < body.progress), body.progress), else_=Task.progress
        ),
        stage=case((newer, body.stage), else_=Task.stage),
        prompt_id=case((newer, body.prompt_id or Task.prompt_id), else_=Task.prompt_id),
    )
    result = db.execute(
        update(Task)
        .where(
            Task.id == task.id,
            Task.status == Status.RUNNING,
            Task.lease_expires_at > now,
            Task.lease_hash == task.lease_hash,
        )
        .values(**values)
    )
    if not cast(CursorResult, result).rowcount:
        task = fence(db, task_id, machine, x_task_lease, terminal=True)
        if task.status == Status.SUCCEEDED:
            return task_read(task)
        raise HTTPException(409, "任务租约已失效")
    if body.sequence > prior_sequence:
        execution = execution_at(db, task, body.execution_index)
        if execution.status in Status.ACTIVE:
            execution.status = Status.RUNNING
            execution.prompt_id = body.prompt_id or execution.prompt_id
            execution.updated_at = now
    db.execute(
        update(Machine)
        .where(Machine.id == machine.id, Machine.revoked_at.is_(None))
        .values(busy_until=until, last_seen=now)
    )
    db.commit()
    db.refresh(task)
    return task_read(task)


@router.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete(task_id: str, db: DB, machine: CurrentMachine, x_task_lease: Lease = None) -> TaskRead:
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.SUCCEEDED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, "任务已结束")
    if not db.scalar(select(task_executions_complete()).where(Task.id == task.id)):
        raise HTTPException(409, "执行尚未完整回传")
    finish_task(db, task, Status.SUCCEEDED)
    db.commit()
    return task_read(task)


# 绑定本次执行的 ComfyUI prompt ID，重复使用同一 ID 可重试，换用其他 ID 返回 409。
@router.post("/tasks/{task_id}/executions/{index}/start", response_model=ExecutionRead)
def start_execution(
    task_id: str,
    index: int,
    body: ExecutionStart,
    db: DB,
    machine: CurrentMachine,
    x_task_lease: Lease = None,
):
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.FAILED:
        raise HTTPException(409, "任务已结束")
    execution = execution_at(db, task, index)
    if execution.prompt_id and execution.prompt_id != body.prompt_id:
        raise HTTPException(409, "执行编号已绑定其他 ComfyUI 任务")
    if execution.status == Status.SUCCEEDED and execution.prompt_id == body.prompt_id:
        return execution_reads(db, [(execution, task)])[0]
    if task.status != Status.RUNNING or execution.status not in Status.ACTIVE:
        raise HTTPException(409, "执行已结束")
    execution.prompt_id = body.prompt_id
    if execution.status == Status.QUEUED:
        execution.status = Status.RUNNING
    execution.updated_at = now_ms()
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


# `client_ids` 是按输出顺序提交的回传编号。最后一组清单确认时同时完成任务并释放工作机。
@router.post("/tasks/{task_id}/executions/{index}/complete", response_model=ExecutionRead)
def complete_execution(
    task_id: str,
    index: int,
    body: ExecutionComplete,
    db: DB,
    machine: CurrentMachine,
    x_task_lease: Lease = None,
):
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.FAILED:
        raise HTTPException(409, "任务已结束")
    execution = execution_at(db, task, index)
    if task.status == Status.SUCCEEDED and execution.status != Status.SUCCEEDED:
        raise HTTPException(409, "执行已结束")
    if not execution.prompt_id:
        raise HTTPException(409, "执行尚未开始")
    finish_execution(db, execution, body.client_ids)
    if task.status == Status.RUNNING and db.scalar(
        select(task_executions_complete()).where(Task.id == task.id)
    ):
        finish_task(db, task, Status.SUCCEEDED)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


@router.post("/tasks/{task_id}/fail", response_model=TaskRead)
def fail(
    task_id: str, body: WorkerFailure, db: DB, machine: CurrentMachine, x_task_lease: Lease = None
) -> TaskRead:
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.FAILED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, "任务已结束")
    finish_task(db, task, Status.FAILED, body.error)
    db.commit()
    return task_read(task)
