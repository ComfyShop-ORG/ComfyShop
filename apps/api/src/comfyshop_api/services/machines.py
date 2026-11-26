"""校验工作机身份和任务租约，管理在线状态、过期任务与机器占用。"""

import hashlib
import json
import secrets
from typing import Annotated, Literal, cast
from uuid import uuid4

from comfyshop_worker_protocol import ERROR_CODE_HEADER, LEASE_HEADER, TASK_CANCELLED
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import (
    ColumnElement,
    Select,
    SQLColumnExpression,
    and_,
    case,
    delete,
    func,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Execution,
    Machine,
    MachineLink,
    OfficialTakeoverWait,
    OfficialWorkerPoll,
    Status,
    Task,
    Team,
    TeamMachinePreference,
    UserPreference,
    now_ms,
)
from comfyshop_api.schemas import (
    MachineCatalog,
    MachineCurrentTask,
    MachineDetail,
    MachineHeartbeat,
    MachineRead,
    MachineUpdate,
    WorkerRelease,
    WorkerRuntime,
)
from comfyshop_api.security import DB, Config, digest, owned_record, workspace_records
from comfyshop_api.services.executions import fail_unfinished_executions, task_executions_complete
from comfyshop_api.services.web_push import enqueue_task_notification
from comfyshop_api.services.worker_releases import published_worker, worker_archive_bytes
from comfyshop_api.services.worker_types import (
    WORKERS,
    personal_worker_kinds,
    route,
    worker_type,
)

bearer = HTTPBearer(auto_error=False, scheme_name="WorkMachineKey")
UPDATE_IN_PROGRESS = {"pending", "updating"}


def new_key() -> tuple[str, str, str]:
    """返回原始密钥、供数据库保存的摘要和供界面识别的前缀。原始密钥只在发放时显示。"""
    raw = "cs_" + secrets.token_urlsafe(36)
    return raw, digest(raw), raw[:11]


def machine_scope(owner_id: str, team_id: str | None) -> ColumnElement[bool]:
    return workspace_records(Machine.owner_id, Machine.team_id, owner_id, team_id)


def owned_machine(
    db: Session,
    machine_id: str,
    owner_id: str,
    *,
    team_id: str | None = None,
    include_deleted: bool = False,
) -> Machine:
    missing = msg("machine.notFound")
    machine = owned_record(db, Machine, machine_id, owner_id, missing, team_id=team_id)
    if machine.deleted_at is not None and not include_deleted:
        raise HTTPException(404, missing)
    return machine


def machine_preference(
    db: Session, owner_id: str, team_id: str | None
) -> UserPreference | TeamMachinePreference | None:
    if team_id is not None:
        return db.get(TeamMachinePreference, team_id)
    return db.get(UserPreference, owner_id)


def set_default_machine(db: Session, machine: Machine, *, only_if_unset: bool = False) -> None:
    pref = machine_preference(db, machine.owner_id, machine.team_id)
    if pref is None:
        pref = (
            TeamMachinePreference(team_id=machine.team_id)
            if machine.team_id is not None
            else UserPreference(user_id=machine.owner_id)
        )
        db.add(pref)
    if not only_if_unset or not pref.default_machine_id:
        pref.default_machine_id = machine.id


def active_machine_team(db: Session, team_id: str) -> bool:
    return (
        db.scalar(select(Team.id).where(Team.id == team_id, Team.archived_at.is_(None))) is not None
    )


def create_machine(
    db: Session, owner_id: str, name: str, *, team_id: str | None = None
) -> tuple[Machine, str]:
    """为空间新建工作机并返回原始密钥。第一台工作机成为默认工作机。"""
    raw, hashed, prefix = new_key()
    machine = Machine(
        owner_id=owner_id, team_id=team_id, name=name.strip(), key_hash=hashed, key_prefix=prefix
    )
    db.add(machine)
    db.flush()
    set_default_machine(db, machine, only_if_unset=True)
    return machine, raw


def stop_assignments(db: Session, machine: Machine, *, revoking: bool) -> None:
    """密钥失效时结束这台工作机持有租约的任务并释放占用，由调用方提交。

    执行中的任务由旧密钥持有租约，结果无法再回传，标记失败。排队的任务还没交给工作机：
    重置密钥后继续等待这台工作机；`revoking` 撤销时再没有机器能领取，同样标记失败。
    """
    statuses = Status.ACTIVE if revoking else (Status.RUNNING,)
    for task_id in db.scalars(
        select(Task.id).where(Task.machine_id == machine.id, Task.status.in_(statuses))
    ):
        fail_unfinished_executions(db, task_id, Status.FAILED)
    db.execute(
        update(Task)
        .where(Task.machine_id == machine.id, Task.status.in_(statuses))
        .values(
            status=Status.FAILED,
            stage="failed",
            error="工作机密钥已撤销或重置",
            updated_at=now_ms(),
        )
    )
    machine.busy_until = 0


def rotate_key(db: Session, machine: Machine) -> str:
    """换发密钥并返回原始密钥，由调用方提交。已撤销的工作机随之恢复，账号没有默认工作机时设为默认。"""
    if worker_type(machine.worker_kind).connection != "machine":
        raise HTTPException(409, msg("connection.editKey"))
    stop_assignments(db, machine, revoking=False)
    raw, machine.key_hash, machine.key_prefix = new_key()
    machine.last_seen = None
    machine.runtime_info = machine.update_info = None
    if machine.revoked_at:
        machine.revoked_at = None
        set_default_machine(db, machine, only_if_unset=True)
    return raw


def reset_key(db: Session, machine: Machine) -> str:
    """用户在网页重置密钥：换发密钥，并删除指向这台工作机的接入申请。由调用方提交。

    申请凭据此后不能再换取密钥，拿到申请凭据的人抢不走用户刚重置的密钥。
    """
    _forget_links(db, machine)
    return rotate_key(db, machine)


def _forget_links(db: Session, machine: Machine) -> None:
    db.execute(
        delete(MachineLink).where(
            or_(
                MachineLink.machine_id == machine.id, MachineLink.reconnect_machine_id == machine.id
            )
        )
    )


def revoke(db: Session, machine: Machine) -> None:
    """撤销工作机的密钥并结束它的全部任务，它是默认工作机时清除默认设置。由调用方提交。"""
    _forget_links(db, machine)
    stop_assignments(db, machine, revoking=True)
    machine.credential = None
    machine.revoked_at = now_ms()
    machine.update_info = None
    pref = machine_preference(db, machine.owner_id, machine.team_id)
    if pref and pref.default_machine_id == machine.id:
        pref.default_machine_id = None


def delete_revoked(machine: Machine) -> None:
    """在调用方锁定的账号下删除已撤销的工作机，由调用方提交。"""
    if machine.revoked_at is None:
        raise HTTPException(409, msg("machine.revokeTheWorkMachineFirst"))
    machine.mark_deleted()


def revoke_all(db: Session, owner_id: str) -> None:
    """撤销账号的全部工作机，用于改密码、重置密码和注销。由调用方提交。"""
    for machine in db.scalars(
        select(Machine).where(machine_scope(owner_id, None), Machine.revoked_at.is_(None))
    ):
        revoke(db, machine)


def set_paused(db: Session, machine: Machine, paused: bool) -> None:
    """与领取任务串行化，只更新工作机的接单设置。由调用方提交。"""
    write_lock(db, Machine, machine.id)
    db.refresh(machine, attribute_names=["revoked_at", "paused"])
    if machine.revoked_at is not None:
        raise HTTPException(409, msg("machine.workMachineRevoked"))
    machine.paused = paused


def machine_is_online(last_seen: int | None, revoked_at: int | None, now: int) -> bool:
    return last_seen is not None and last_seen > now - 45_000 and revoked_at is None


def _active_update(machine: Machine) -> MachineUpdate | None:
    if machine.update_info and machine.update_info.get("status") in UPDATE_IN_PROGRESS:
        return MachineUpdate.model_validate(machine.update_info)
    return None


def _has_update(runtime: WorkerRuntime | None, release: WorkerRelease | None) -> bool:
    return bool(
        runtime
        and runtime.can_update
        and release
        and tuple(map(int, release.version.split(".")))
        > tuple(map(int, runtime.version.split(".")))
    )


def _queue_update(machine: Machine) -> None:
    machine.update_info = MachineUpdate(id=str(uuid4()), status="pending").model_dump()


def machine_read(machine: Machine, release: WorkerRelease | None = None) -> MachineRead:
    now = now_ms()
    online = (
        not machine.revoked_at
        if worker_type(machine.worker_kind).connection == "account"
        else machine_is_online(machine.last_seen, machine.revoked_at, now)
    )
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    return MachineRead(
        worker=route(machine.worker_kind, machine.connection_scope),
        id=machine.id,
        name=machine.name,
        key_prefix=machine.key_prefix,
        device=machine.device,
        operating_system=machine.capabilities.get("operating_system"),
        online=online,
        busy=machine.busy_until > now,
        paused=machine.paused,
        revoked=bool(machine.revoked_at),
        last_seen=machine.last_seen,
        node_count=len(machine.capabilities.get("nodes", [])),
        catalog_synced_at=machine.catalog_synced_at,
        comfy_status=machine.comfy_status if online else None,
        startup_issue=machine.startup_issue,
        startup_issue_at=machine.startup_issue_at,
        runtime=runtime,
        update=MachineUpdate.model_validate(machine.update_info) if machine.update_info else None,
        update_available=not machine.revoked_at
        and not _active_update(machine)
        and _has_update(runtime, release),
    )


def machine_detail(db: Session, machine: Machine, release: WorkerRelease | None) -> MachineDetail:
    """按同一份任务快照读取排队数和当前租约有效的任务。"""
    assigned = (
        workspace_records(Task.owner_id, Task.team_id, machine.owner_id, machine.team_id),
        Task.machine_id == machine.id,
        Task.visible(),
    )
    queued = (
        select(func.count(Task.id).label("queued_count"))
        .where(*assigned, Task.status == Status.QUEUED)
        .subquery()
    )
    current = (
        select(Task.id, Task.workflow_name, Task.stage, Task.progress)
        .where(*assigned, Task.status == Status.RUNNING, Task.lease_expires_at > now_ms())
        .order_by(Task.created_at.desc(), Task.id.desc())
        .limit(1)
        .subquery()
    )
    row = db.execute(select(queued, current).select_from(queued.outerjoin(current, true()))).one()
    return MachineDetail(
        machine=machine_read(machine, release),
        current_task=MachineCurrentTask.model_validate(row) if row.id is not None else None,
        queued_count=row.queued_count,
    )


def _invalid_key() -> HTTPException:
    return HTTPException(
        401, msg("machine.invalidWorkMachineKey"), headers={"WWW-Authenticate": "Bearer"}
    )


def _connection_update(db: Session, machine: Machine, **values: object) -> None:
    result = db.execute(
        update(Machine)
        .where(
            Machine.id == machine.id,
            Machine.key_hash == machine.key_hash,
            Machine.revoked_at.is_(None),
        )
        .values(**values)
    )
    if not cast(CursorResult, result).rowcount:
        raise _invalid_key()
    db.refresh(machine)


def record_heartbeat(db: Session, machine: Machine, body: MachineHeartbeat) -> None:
    """记录工作机心跳，写入时复核密钥，避免换发前已通过认证的心跳更新新连接。"""
    stamp = now_ms()
    runtime = body.runtime
    _connection_update(
        db,
        machine,
        **({"device": body.device} if "device" in body.model_fields_set else {}),
        last_seen=stamp,
        comfy_status=body.comfy_status,
        runtime_info=runtime.model_dump(exclude={"failure", "checking"}),
        **(
            {"startup_issue": body.startup_issue, "startup_issue_at": stamp}
            if body.startup_issue
            else {}
        ),
    )
    capabilities = {**machine.capabilities, "operating_system": body.operating_system}
    if "nodes" in body.model_fields_set:
        capabilities["nodes"] = body.nodes
    machine.capabilities = capabilities
    pending = _active_update(machine)
    if not pending:
        return
    if (
        pending.release
        and runtime.version == pending.release.version
        and runtime.build == pending.release.build
    ):
        pending.status = "succeeded"
    elif runtime.failure and runtime.failure.id == pending.id:
        pending.status = "failed"
        pending.error = runtime.failure.reason
    elif not runtime.can_update:
        pending.status = "failed"
        pending.error = "当前启动方式无法继续更新"
    machine.update_info = pending.model_dump()


def record_catalog(db: Session, machine: Machine, body: MachineCatalog) -> str:
    nodes = {name: node.model_dump() for name, node in body.nodes.items()}
    encoded = json.dumps(nodes, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > 8 * 1024 * 1024:
        raise HTTPException(413, msg("media.theNodeCatalogIsTooLarge"))
    digest_value = hashlib.sha256(encoded).hexdigest()
    _connection_update(
        db, machine, catalog=nodes, catalog_hash=digest_value, catalog_synced_at=now_ms()
    )
    return digest_value


def request_update(db: Session, machine: Machine, release: WorkerRelease | None) -> None:
    """请求工作机空闲后更新到最新版，重复请求沿用当前更新。"""
    write_lock(db, Machine, machine.id)
    db.refresh(machine)
    if machine.revoked_at:
        raise HTTPException(409, msg("machine.workMachineRevoked"))
    if _active_update(machine):
        return
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    if not _has_update(runtime, release):
        raise HTTPException(409, msg("machine.noUpdatesAreAvailableForThis"))
    _queue_update(machine)


def start_update(
    db: Session, machine: Machine, update_id: str, settings: Settings
) -> WorkerRelease:
    """工作机交还任务后，读取当时可用的最新签名发布包。"""
    _connection_update(db, machine, last_seen=now_ms())
    pending = _active_update(machine)
    if not pending or pending.id != update_id:
        raise HTTPException(409, msg("machine.theUpdateRequestExpired"))
    if machine.busy_until > now_ms():
        raise HTTPException(409, msg("machine.waitForTheCurrentTaskTo"))
    published = published_worker(settings)
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    if published is None or not _has_update(runtime, published.release):
        raise HTTPException(409, msg("machine.noUpdatesAreAvailableForThis"))
    pending.status = "updating"
    pending.release = published.release
    machine.update_info = pending.model_dump()
    return published.release


def download_update(db: Session, machine: Machine, sha256: str, settings: Settings) -> bytes | None:
    """读取获准下载的签名包。返回 None 表示发布已切换，更新已重新排队。"""
    _connection_update(db, machine, last_seen=now_ms())
    pending = _active_update(machine)
    if (
        pending is None
        or pending.status != "updating"
        or pending.release is None
        or pending.release.sha256 != sha256
    ):
        raise HTTPException(404, msg("machine.updatePackageNotFound"))

    published = published_worker(settings)
    if published and published.release.sha256 == sha256:
        try:
            return worker_archive_bytes(settings, pending.release)
        except FileNotFoundError:
            published = published_worker(settings)
        except (OSError, ValueError):
            raise HTTPException(503, msg("machine.couldNotVerifyOrReadThe")) from None
    if published is None or published.release.sha256 == sha256:
        raise HTTPException(503, msg("machine.theUpdatePackageIsTemporarilyUnavailable"))
    # 启动器会恢复原版本。新请求 ID 让上次下载失败的回报不会结束这次更新。
    _queue_update(machine)
    return None


def authenticate_machine(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Machine:
    machine = (
        db.scalar(select(Machine).where(Machine.key_hash == digest(credentials.credentials)))
        if credentials
        else None
    )
    if (
        not machine
        or machine.revoked_at
        or worker_type(machine.worker_kind).connection != "machine"
        or (machine.team_id is not None and not active_machine_team(db, machine.team_id))
    ):
        raise _invalid_key()
    return machine


CurrentMachine = Annotated[Machine, Depends(authenticate_machine)]
WorkerIdentity = Machine | str


def authenticate_task_worker(
    db: DB,
    config: Config,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> WorkerIdentity:
    if credentials:
        for definition in WORKERS.values():
            token = config.worker_service_tokens.get(definition.kind)
            if (
                definition.service
                and token
                and secrets.compare_digest(
                    token.get_secret_value().encode(), credentials.credentials.encode()
                )
            ):
                return definition.kind
    return authenticate_machine(db, credentials)


CurrentWorker = Annotated[WorkerIdentity, Depends(authenticate_task_worker)]


def require_service_worker(worker: CurrentWorker) -> str:
    if not isinstance(worker, str):
        raise HTTPException(403)
    return worker


ServiceWorker = Annotated[str, Depends(require_service_worker)]

# 工作机 API Key 识别机器，任务操作还需提供对应领取产生的租约凭据。
Lease = Annotated[str | None, Header(alias=LEASE_HEADER)]


def expire_leases(db: Session) -> None:
    """结束租约过期的任务。清单齐全时补记成功，其余标记失败并保留成功的执行。

    先用只读查询按索引找出到期任务，没有到期任务时不写入，也就不取得写锁。
    """
    # An ambiguous GPU run must never be automatically submitted a second time.
    now = now_ms()
    expired = (
        Task.worker_kind.in_(personal_worker_kinds()),
        Task.status == Status.RUNNING,
        Task.lease_expires_at <= now,
    )
    task_ids = list(db.scalars(select(Task.id).where(*expired)))
    if not task_ids:
        return
    complete = task_executions_complete()
    status = case((complete, Status.SUCCEEDED), else_=Status.FAILED)
    result = db.execute(
        update(Task)
        .where(Task.id.in_(task_ids), *expired)
        .values(
            status=status,
            stage=status,
            progress=case((complete, 100), else_=Task.progress),
            error=case((complete, None), else_="工作机连接中断，请检查连接后重新提交"),
            updated_at=now,
        )
    )
    if cast(CursorResult, result).rowcount:
        # 补记成功的任务没有未结束的执行，这里只会结束失败任务里尚未完成的执行。
        db.execute(
            update(Execution)
            .where(Execution.task_id.in_(task_ids), Execution.status.in_(Status.ACTIVE))
            .where(
                Execution.task_id.in_(
                    select(Task.id).where(Task.id.in_(task_ids), Task.status == Status.FAILED)
                )
            )
            .values(status=Status.FAILED, updated_at=now)
        )
    db.commit()


def claimed_task(db: Session, task_id: str, machine: WorkerIdentity, lease: str | None) -> Task:
    """核对已领取任务的原工作机和租约凭据，时效由各操作检查。"""
    task = db.get(Task, task_id, populate_existing=True)
    if not task or task.worker_kind != (
        machine.worker_kind if isinstance(machine, Machine) else machine
    ):
        raise HTTPException(404, msg("task.notFound"))
    if isinstance(machine, Machine) and (
        task.machine_id != machine.id
        or task.team_id != machine.team_id
        or (task.team_id is None and task.owner_id != machine.owner_id)
    ):
        raise HTTPException(404, msg("task.notFound"))
    if not lease or not secrets.compare_digest(task.lease_hash or "", digest(lease)):
        raise HTTPException(409, msg("machine.invalidTaskLease"))
    return task


def fence(
    db: Session, task_id: str, machine: WorkerIdentity, lease: str | None, *, terminal: bool = False
) -> Task:
    """检查当前租约；terminal 允许使用原凭据确认已成功或失败的任务。"""
    task = claimed_task(db, task_id, machine, lease)
    if terminal and task.status in {Status.SUCCEEDED, Status.FAILED}:
        return task
    if task.status == Status.CANCELLED:
        raise HTTPException(409, msg("task.canceled"), headers={ERROR_CODE_HEADER: TASK_CANCELLED})
    if task.status != Status.RUNNING or (task.lease_expires_at or 0) <= now_ms():
        raise HTTPException(409, msg("media.theTaskLeaseExpired"))
    return task


def claim_task(
    db: Session, machine: Machine, claim_id: str, secret: str, lease_seconds: int
) -> tuple[Task | None, bool]:
    """为空闲的工作机领取最早排队的任务，返回任务及是否为新领取。

    `claim_id` 与 `secret` 由工作机先持久化，重试同一次领取返回原任务。机器暂停接单、
    繁忙或没有可领任务时返回 `(None, False)`。新领取的占用和租约由调用方提交。
    """
    expire_leases(db)
    prior = db.scalar(select(Task).where(Task.claim_id == claim_id))
    if prior:
        return fence(db, prior.id, machine, secret), False
    now = now_ms()
    until = now + lease_seconds * 1000
    locked = db.execute(
        update(Machine)
        .where(
            Machine.id == machine.id,
            # 认证后密钥刚被重置或撤销时，旧密钥的这次领取不能拿到任务。
            Machine.key_hash == machine.key_hash,
            Machine.revoked_at.is_(None),
            Machine.paused.is_(False),
            Machine.busy_until <= now,
        )
        .values(busy_until=until, last_seen=now)
    )
    if not cast(CursorResult, locked).rowcount:
        db.rollback()
        return None, False
    # 同一次领取的恢复已在上面处理。用户请求更新后暂停新的领取。
    db.refresh(machine, attribute_names=["update_info"])
    if _active_update(machine):
        db.rollback()
        return None, False
    scope = workspace_records(Task.owner_id, Task.team_id, machine.owner_id, machine.team_id)
    task_id = db.scalar(
        select(Task.id)
        .where(
            Task.machine_id == machine.id,
            scope,
            Task.worker_kind == machine.worker_kind,
            Task.status == Status.QUEUED,
            Task.visible(),
        )
        .order_by(Task.queued_at, Task.id)
        .limit(1)
    )
    if not task_id:
        db.rollback()
        return None, False
    updated = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.machine_id == machine.id,
            scope,
            Task.worker_kind == machine.worker_kind,
            Task.status == Status.QUEUED,
            Task.visible(),
        )
        .values(
            status=Status.RUNNING,
            stage="preflight",
            claim_id=claim_id,
            lease_hash=digest(secret),
            lease_expires_at=until,
            updated_at=now,
        )
    )
    if not cast(CursorResult, updated).rowcount:
        db.rollback()
        return None, False
    task = db.get(Task, task_id, populate_existing=True)
    if task is None:
        raise HTTPException(404, msg("task.notFound"))
    return task, True


def service_task_claimable(
    task: type[Task], now: int, kind: str | SQLColumnExpression[str]
) -> ColumnElement[bool]:
    """领取和计算队列位置使用同一工作机类型及租约条件。"""
    return and_(
        task.worker_kind == kind,
        Team.active_scope(task.team_id),
        task.visible(),
        or_(
            task.status == Status.QUEUED,
            and_(task.status == Status.RUNNING, task.lease_expires_at <= now),
        ),
    )


def last_takeover_wait_number(task_id: str | SQLColumnExpression[str]) -> Select[tuple[int]]:
    return select(func.coalesce(func.max(OfficialTakeoverWait.number), 0)).where(
        OfficialTakeoverWait.task_id == task_id
    )


def record_official_wait(
    db: Session, task: Task, ended_at: int, outcome: Literal["resumed", "ended"]
) -> None:
    """调用方持有任务写锁，在覆盖旧租约或结束任务之前保存等待。"""
    started_at = task.lease_expires_at
    if (
        not worker_type(task.worker_kind).tracks_takeover
        or task.status != Status.RUNNING
        or started_at is None
        or started_at > ended_at
    ):
        return
    number = db.execute(last_takeover_wait_number(task.id)).scalar_one() + 1
    db.add(
        OfficialTakeoverWait(
            task_id=task.id,
            number=number,
            started_at=started_at,
            ended_at=ended_at,
            outcome=outcome,
        )
    )


def record_service_poll(db: Session, adapters: list[str], now: int) -> None:
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    poll = insert(OfficialWorkerPoll).values(
        [{"adapter": adapter, "last_polled_at": now} for adapter in sorted(set(adapters))]
    )
    db.execute(
        poll.on_conflict_do_update(
            index_elements=[OfficialWorkerPoll.adapter],
            set_={"last_polled_at": poll.excluded.last_polled_at},
            where=OfficialWorkerPoll.last_polled_at < poll.excluded.last_polled_at,
        )
    )


def claim_service_task(
    db: Session,
    claim_id: str,
    secret: str,
    lease_seconds: int,
    adapters: list[str],
    kind: str,
) -> tuple[Task | None, bool]:
    now = now_ms()
    definition = worker_type(kind)
    if definition.tracks_takeover:
        record_service_poll(db, adapters, now)
    # 同一适配器的接单已串行。并发重试相同领取编号时，后到的请求读取已发放的租约。
    prior = db.scalar(select(Task).where(Task.claim_id == claim_id))
    if prior:
        return fence(db, prior.id, kind, secret), False
    if definition.form == "nodes" and set(adapters).isdisjoint(definition.adapters or (kind,)):
        return None, False
    eligible = (
        service_task_claimable(Task, now, kind),
        Task.input_graph["adapter"].as_string().in_(adapters)
        if definition.form == "fields"
        else true(),
    )
    first = select(Task.id).where(*eligible).order_by(Task.queued_at, Task.id).limit(1)
    task_id = db.scalar(
        update(Task)
        .where(Task.id == first.scalar_subquery(), *eligible)
        .values(claim_id=claim_id, lease_hash=digest(secret))
        .returning(Task.id)
        .execution_options(synchronize_session=False)
    )
    if task_id is None:
        return None, False
    # 条件更新已锁定该任务。旧租约的结束时间与新租约在同一事务中交接。
    task = db.get_one(Task, task_id, populate_existing=True)
    claimed_at = max(now, now_ms())
    record_official_wait(db, task, claimed_at, "resumed")
    task.official_taken_over = definition.tracks_takeover and task.status == Status.RUNNING
    task.status = Status.RUNNING
    task.stage = "preflight"
    task.lease_expires_at = claimed_at + lease_seconds * 1000
    task.updated_at = claimed_at
    return task, True


def lock_leased_task(db: Session, task_id: str, machine: WorkerIdentity, lease: str | None) -> Task:
    """在当前事务里串行化任务状态写入，再核对最新租约。失败行为见 `fence`。"""
    task = fence(db, task_id, machine, lease, terminal=True)
    if task.status == Status.RUNNING:
        # 条件更新取得写锁，使执行和任务的状态转换串行，再按最新状态核对租约。
        db.execute(
            update(Task)
            .where(Task.id == task_id, Task.status == Status.RUNNING)
            .values(updated_at=now_ms())
        )
        task = fence(db, task_id, machine, lease, terminal=True)
    return task


def finish_task(
    db: Session,
    task: Task,
    status: Literal[Status.SUCCEEDED, Status.FAILED],
    error: str | None = None,
) -> None:
    now = now_ms()
    record_official_wait(db, task, now, "ended")
    task.status = status
    task.stage = status
    task.error = error
    task.updated_at = now
    if status == Status.SUCCEEDED:
        task.progress = 100
        enqueue_task_notification(db, task, now)
    else:
        fail_unfinished_executions(db, task.id, status)
    # 释放与本任务租约对应的占用，避免结束旧任务时清掉新任务已取得的占用。
    db.execute(
        update(Machine)
        .where(Machine.id == task.machine_id, Machine.busy_until == task.lease_expires_at)
        .values(busy_until=0, last_seen=now)
    )
