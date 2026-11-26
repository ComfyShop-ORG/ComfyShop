"""工作机协议入口，接收节点目录、心跳、任务领取和执行清单。"""

import json
from io import BytesIO
from typing import Annotated, Any, cast
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from comfyshop_worker_protocol import RECOVERY_HEADER
from fastapi import APIRouter, Header, HTTPException, Request, Response
from sqlalchemy import case, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import (
    Asset,
    Execution,
    Machine,
    Status,
    Task,
    TaskAsset,
    now_ms,
)
from comfyshop_api.schemas import (
    ClaimRequest,
    ErrorRead,
    ExecutionComplete,
    ExecutionRead,
    ExecutionStart,
    JobAsset,
    JobExecution,
    JobRead,
    MachineCatalog,
    MachineHeartbeat,
    MachineLinkRequest,
    MachineLinkResult,
    MachineLinkStart,
    MachineLinkToken,
    MachineRead,
    OfficialExecutionFailure,
    ServiceClaimRequest,
    ServiceJobRead,
    TaskRead,
    WorkerDigest,
    WorkerEvent,
    WorkerFailure,
    WorkerRecovery,
    WorkerRecoveryRead,
    WorkerRelease,
)
from comfyshop_api.security import DB, Config, client_address, throttle
from comfyshop_api.services.connections import credentials as task_credentials
from comfyshop_api.services.executions import (
    execution_at,
    execution_reads,
    execution_seed_bindings,
    fail_official_execution,
    finish_execution,
    task_executions_complete,
)
from comfyshop_api.services.machine_links import (
    LINK_TTL_MS,
    POLL_SECONDS,
    redeem_link,
    request_link,
)
from comfyshop_api.services.machines import (
    CurrentMachine,
    CurrentWorker,
    Lease,
    ServiceWorker,
    claim_service_task,
    claim_task,
    download_update,
    fence,
    finish_task,
    lock_leased_task,
    machine_read,
    record_catalog,
    record_heartbeat,
    start_update,
)
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.parameter_features import qwen_prompt_preview
from comfyshop_api.services.recovery import prepare_recovery, recovery_execution
from comfyshop_api.services.tasks import task_read
from comfyshop_api.services.worker_releases import published_worker_package
from comfyshop_api.services.worker_types import worker_type

router = APIRouter(prefix="/worker", tags=["worker"])


# 下载工作机启动包。包内附带平台地址，解压后直接启动即可申请接入。
@router.get("/package")
def download_package(request: Request, settings: Config) -> Response:
    try:
        signed = published_worker_package(settings)
    except (OSError, ValueError):
        raise HTTPException(503, msg("media.couldNotVerifyOrReadThe")) from None
    if signed:
        published, content = signed
    else:
        published = None
        source = settings.static_dir and settings.static_dir / "downloads" / "comfyshop-worker.zip"
        if not source or not source.is_file():
            raise HTTPException(404, msg("media.theWorkMachinePackageIsNot"))
        content = source.read_bytes()
    package = BytesIO(content)
    with ZipFile(package, "a", compression=ZIP_DEFLATED) as bundle:
        root = bundle.namelist()[0].split("/", 1)[0]
        entry = ZipInfo(f"{root}/worker.json")
        entry.external_attr = 0o100600 << 16
        bundle.writestr(
            entry,
            json.dumps(
                {
                    "serverUrl": settings.platform_url(str(request.base_url)),
                    "comfyUrl": "http://127.0.0.1:8188",
                },
                indent=2,
            ),
        )
        if published:
            public_key = ZipInfo(f"{root}/worker-release.pub")
            public_key.external_attr = 0o100644 << 16
            bundle.writestr(public_key, published.public_key + "\n")
    return Response(
        package.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="comfyshop-worker.zip"'},
    )


# 首次启动的工作机申请接入，等待账号在网页确认。两个入口都不需要登录或密钥，
# 申请按来源地址限制频率，单一来源不能占满全平台的等待名额。
@router.post("/links", status_code=201)
def start_link(body: MachineLinkRequest, request: Request, db: DB) -> MachineLinkStart:
    throttle(request, db, None, "link")
    link, secret = request_link(db, body.name, client_address(request))
    db.commit()
    return MachineLinkStart(
        secret=secret,
        code=link.code,
        verification_path="/machines/link",
        expires_in=LINK_TTL_MS // 1000,
        interval=POLL_SECONDS,
    )


@router.post("/links/token")
def redeem_machine_link(body: MachineLinkToken, db: DB) -> MachineLinkResult:
    redeemed = redeem_link(db, body.secret)
    if redeemed is None:
        return MachineLinkResult(status="pending")
    db.commit()
    api_key, name = redeemed
    return MachineLinkResult(status="approved", api_key=api_key, machine_name=name)


@router.put("/catalog", response_model=dict[str, str])
def update_catalog(body: MachineCatalog, db: DB, machine: CurrentMachine):
    catalog_hash = record_catalog(db, machine, body)
    db.commit()
    return {"hash": catalog_hash}


@router.post("/heartbeat")
def heartbeat(body: MachineHeartbeat, db: DB, machine: CurrentMachine) -> MachineRead:
    if body.runtime.checking:
        return machine_read(machine)
    record_heartbeat(db, machine, body)
    db.commit()
    return machine_read(machine)


@router.put("/updates/{update_id}")
def begin_update(
    update_id: UUID, db: DB, machine: CurrentMachine, settings: Config
) -> WorkerRelease:
    release = start_update(db, machine, str(update_id), settings)
    db.commit()
    return release


@router.get(
    "/releases/{sha256}",
    response_class=Response,
    responses={
        200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}},
        410: {"model": ErrorRead, "description": "发布包已替换，工作机将重新获取最新版"},
        503: {"model": ErrorRead},
    },
)
def get_update_package(
    sha256: WorkerDigest, settings: Config, db: DB, machine: CurrentMachine
) -> Response:
    content = download_update(db, machine, sha256, settings)
    db.commit()
    if content is None:
        raise HTTPException(410, msg("media.theWorkMachineReleaseChangedDownloading"))
    return Response(content, media_type="application/zip")


def job_read(db: Session, task: Task, config: Settings) -> JobRead:
    assert task.lease_expires_at is not None
    definition = worker_type(task.worker_kind)
    preview = None if definition.service else qwen_prompt_preview(task.input_graph)
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
        worker_context={
            **task.worker_data,
            "fields": [
                {"id": f["id"], "nodeId": f["node_id"], "name": f["input_name"], "kind": f["kind"]}
                for f in task.input_schema.get("fields", [])
            ],
        }
        if task.worker_data
        else {},
        graph=task.input_graph,
        lease_expires_at=task.lease_expires_at,
        assets=assets,
        execution_seeds=[] if definition.form == "fields" else execution_seed_bindings(db, task),
        prompt_preview_node_id=preview[0] if preview else None,
        recovery_window_seconds=config.failed_artifact_ttl_seconds,
        max_artifact_bytes=config.max_artifact_bytes,
    )


# `claim_id` 与租约凭据用于重试同一次领取。暂停接单、机器繁忙或无可领任务时返回 JSON null。
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
    job = job_read(db, task, config)
    if new_claim:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, msg("media.thisTaskCouldNotBeClaimed")) from None
    return job


@router.post("/tasks/{task_id}/heartbeat")
def task_heartbeat(
    task_id: str,
    body: WorkerEvent,
    db: DB,
    machine: CurrentWorker,
    config: Config,
    x_task_lease: Lease = None,
) -> TaskRead:
    task = fence(db, task_id, machine, x_task_lease, terminal=True)
    if task.status == Status.SUCCEEDED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, msg("media.theTaskLeaseExpired"))
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
    )
    if isinstance(machine, Machine):
        values["prompt_id"] = case((newer, body.prompt_id or Task.prompt_id), else_=Task.prompt_id)
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
        raise HTTPException(409, msg("media.theTaskLeaseExpired"))
    if body.sequence > prior_sequence:
        execution = execution_at(db, task, body.execution_index)
        if execution.status in Status.ACTIVE:
            execution.status = Status.RUNNING
            if isinstance(machine, Machine):
                execution.prompt_id = body.prompt_id or execution.prompt_id
            execution.updated_at = now
    if isinstance(machine, Machine):
        db.execute(
            update(Machine)
            .where(Machine.id == machine.id, Machine.revoked_at.is_(None))
            .values(busy_until=until, last_seen=now)
        )
    db.commit()
    db.refresh(task)
    return task_read(task)


@router.get("/tasks/{task_id}/connection")
def leased_connection(
    task_id: str,
    db: DB,
    config: Config,
    response: Response,
    worker: ServiceWorker,
    x_task_lease: Lease = None,
) -> dict[str, str]:
    task = fence(db, task_id, worker, x_task_lease)
    response.headers["Cache-Control"] = "no-store"
    return task_credentials(db, task, config)


@router.post("/services/{kind}/claim")
def claim_service(
    kind: str, body: ServiceClaimRequest, db: DB, worker: ServiceWorker, config: Config
) -> ServiceJobRead | None:
    if kind != worker:
        raise HTTPException(403)
    try:
        task, new_claim = claim_service_task(
            db,
            body.claim_id,
            body.lease_secret.get_secret_value(),
            config.worker_lease_seconds,
            body.adapters,
            kind,
        )
        if task is None:
            db.commit()
            return None
        job = ServiceJobRead(
            **job_read(db, task, config).model_dump(),
            event_sequence=task.event_seq,
            executions=[
                JobExecution.model_validate(execution)
                for execution in db.scalars(
                    select(Execution).where(Execution.task_id == task.id).order_by(Execution.index)
                )
            ],
        )
        if new_claim:
            db.commit()
        return job
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("media.thisTaskCouldNotBeClaimed")) from None


@router.post("/tasks/{task_id}/executions/{index}/reserve")
def reserve_execution(
    task_id: str, index: int, db: DB, worker: ServiceWorker, x_task_lease: Lease = None
) -> bool:
    task = lock_leased_task(db, task_id, worker, x_task_lease)
    execution = execution_at(db, task, index)
    if task.status != Status.RUNNING or execution.status not in Status.ACTIVE:
        raise HTTPException(409, msg("media.theRunHasEnded"))
    if execution.prompt_id or execution.submission_pending:
        return False
    execution.submission_pending = True
    execution.status = Status.RUNNING
    execution.updated_at = now_ms()
    db.commit()
    return True


@router.post("/tasks/{task_id}/complete")
def complete(task_id: str, db: DB, machine: CurrentWorker, x_task_lease: Lease = None) -> TaskRead:
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.SUCCEEDED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, msg("media.theTaskHasEnded"))
    if not db.scalar(select(task_executions_complete()).where(Task.id == task.id)):
        raise HTTPException(409, msg("media.theRunHasNotFullyUploaded"))
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
    machine: CurrentWorker,
    x_task_lease: Lease = None,
):
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.FAILED:
        raise HTTPException(409, msg("media.theTaskHasEnded"))
    execution = execution_at(db, task, index)
    if execution.prompt_id and execution.prompt_id != body.prompt_id:
        raise HTTPException(409, msg("media.thisRunIsAlreadyAssociatedWith"))
    if execution.status == Status.SUCCEEDED and execution.prompt_id == body.prompt_id:
        return execution_reads(db, [(execution, task)])[0]
    if task.status != Status.RUNNING or execution.status not in Status.ACTIVE:
        raise HTTPException(409, msg("media.theRunHasEnded"))
    if worker_type(task.worker_kind).service:
        if not execution.prompt_id and not execution.submission_pending:
            raise HTTPException(409, msg("media.theRunHasNotStarted"))
        execution.submission_pending = False
        task.prompt_id = body.prompt_id
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
    machine: CurrentWorker,
    config: Config,
    x_task_lease: Lease = None,
    x_task_recovery: Annotated[bool, Header(alias=RECOVERY_HEADER)] = False,
):
    if x_task_recovery:
        if not isinstance(machine, Machine):
            raise HTTPException(403)
        task, execution = recovery_execution(
            db, task_id, index, machine, x_task_lease, config.failed_artifact_ttl_seconds, lock=True
        )
    else:
        task = lock_leased_task(db, task_id, machine, x_task_lease)
        if task.status == Status.FAILED:
            raise HTTPException(409, msg("media.theTaskHasEnded"))
        execution = execution_at(db, task, index)
    if task.status == Status.SUCCEEDED and execution.status != Status.SUCCEEDED:
        raise HTTPException(409, msg("media.theRunHasEnded"))
    if not execution.prompt_id:
        raise HTTPException(409, msg("media.theRunHasNotStarted"))
    if body.effective_prompt is not None and (
        worker_type(task.worker_kind).service or not qwen_prompt_preview(task.input_graph)
    ):
        raise HTTPException(422, msg("media.promptReportingIsUnavailableForThis"))
    finish_execution(
        db, execution, body.client_ids, body.effective_prompt, recovering=x_task_recovery
    )
    if task.status != Status.SUCCEEDED and db.scalar(
        select(task_executions_complete()).where(Task.id == task.id)
    ):
        finish_task(db, task, Status.SUCCEEDED)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


@router.post("/tasks/{task_id}/executions/{index}/fail")
def report_official_execution_failure(
    task_id: str,
    index: int,
    body: OfficialExecutionFailure,
    db: DB,
    worker: ServiceWorker,
    x_task_lease: Lease = None,
) -> None:
    task = lock_leased_task(db, task_id, worker, x_task_lease)
    fail_official_execution(
        task, execution_at(db, task, index), body.error, retryable=body.retryable
    )
    db.commit()


@router.put("/tasks/{task_id}/executions/{index}/recovery")
def report_recovery(
    task_id: str,
    index: int,
    body: WorkerRecovery,
    db: DB,
    machine: CurrentMachine,
    config: Config,
    x_task_lease: Lease = None,
) -> WorkerRecoveryRead:
    result = prepare_recovery(
        db, task_id, index, body, machine, x_task_lease, config.failed_artifact_ttl_seconds
    )
    db.commit()
    return result


@router.post("/tasks/{task_id}/fail")
def fail(
    task_id: str, body: WorkerFailure, db: DB, machine: CurrentWorker, x_task_lease: Lease = None
) -> TaskRead:
    task = lock_leased_task(db, task_id, machine, x_task_lease)
    if task.status == Status.FAILED:
        return task_read(task)
    if task.status != Status.RUNNING:
        raise HTTPException(409, msg("media.theTaskHasEnded"))
    if worker_type(task.worker_kind).service and body.retryable_execution_index is not None:
        execution = execution_at(db, task, body.retryable_execution_index)
        if execution.status in Status.ACTIVE:
            fail_official_execution(task, execution, body.error, retryable=True)
            db.flush()
    finish_task(db, task, Status.FAILED, body.error)
    db.commit()
    return task_read(task)
