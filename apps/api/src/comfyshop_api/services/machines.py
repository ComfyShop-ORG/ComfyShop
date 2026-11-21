"""校验工作机身份和任务租约，管理在线状态、过期任务与机器占用。"""

import secrets
from typing import Annotated, Literal, cast
from uuid import uuid4

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import case, delete, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Status,
    Execution,
    Machine,
    MachineLink,
    Task,
    UserPreference,
    now_ms,
)
from comfyshop_api.schemas import (
    MachineHeartbeat,
    MachineRead,
    MachineUpdate,
    WorkerRelease,
    WorkerRuntime,
    WorkerRuntimeReport,
)
from comfyshop_api.security import DB, digest
from comfyshop_api.services.executions import fail_unfinished_executions, task_executions_complete
from comfyshop_api.services.worker_releases import published_worker, worker_archive_bytes

bearer = HTTPBearer(auto_error=False, scheme_name="WorkMachineKey")
UPDATE_IN_PROGRESS = {"pending", "updating"}


def new_key() -> tuple[str, str, str]:
    """返回原始密钥、供数据库保存的摘要和供界面识别的前缀。原始密钥只在发放时显示。"""
    raw = "cs_" + secrets.token_urlsafe(36)
    return raw, digest(raw), raw[:11]


def create_machine(db: Session, owner_id: str, name: str) -> tuple[Machine, str]:
    """为账号新建工作机并返回它和原始密钥，由调用方提交。账号的第一台工作机成为默认工作机。"""
    raw, hashed, prefix = new_key()
    machine = Machine(owner_id=owner_id, name=name.strip(), key_hash=hashed, key_prefix=prefix)
    db.add(machine)
    db.flush()
    _default_if_unset(db, machine)
    return machine, raw


def _default_if_unset(db: Session, machine: Machine) -> None:
    pref = db.get(UserPreference, machine.owner_id)
    if not pref:
        db.add(UserPreference(user_id=machine.owner_id, default_machine_id=machine.id))
    elif not pref.default_machine_id:
        pref.default_machine_id = machine.id


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
    stop_assignments(db, machine, revoking=False)
    raw, machine.key_hash, machine.key_prefix = new_key()
    machine.last_seen = None
    machine.runtime_info = machine.update_info = None
    if machine.revoked_at:
        machine.revoked_at = None
        _default_if_unset(db, machine)
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
    machine.revoked_at = now_ms()
    machine.update_info = None
    pref = db.get(UserPreference, machine.owner_id)
    if pref and pref.default_machine_id == machine.id:
        pref.default_machine_id = None


def revoke_all(db: Session, owner_id: str) -> None:
    """撤销账号的全部工作机，用于改密码、重置密码和注销。由调用方提交。"""
    for machine in db.scalars(
        select(Machine).where(Machine.owner_id == owner_id, Machine.revoked_at.is_(None))
    ):
        revoke(db, machine)


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
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    return MachineRead(
        id=machine.id,
        name=machine.name,
        key_prefix=machine.key_prefix,
        device=machine.device,
        online=machine_is_online(machine.last_seen, machine.revoked_at, now),
        busy=machine.busy_until > now,
        revoked=bool(machine.revoked_at),
        last_seen=machine.last_seen,
        node_count=len(machine.capabilities.get("nodes", [])),
        runtime=runtime,
        update=MachineUpdate.model_validate(machine.update_info) if machine.update_info else None,
        update_available=not machine.revoked_at
        and not _active_update(machine)
        and _has_update(runtime, release),
    )


def _invalid_key() -> HTTPException:
    return HTTPException(401, "工作机密钥无效", headers={"WWW-Authenticate": "Bearer"})


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


def record_heartbeat(
    db: Session,
    machine: Machine,
    body: MachineHeartbeat,
    runtime: WorkerRuntimeReport | None = None,
) -> None:
    """记录工作机心跳，写入时复核密钥，避免换发前已通过认证的心跳更新新连接。"""
    _connection_update(
        db,
        machine,
        device=body.device,
        capabilities={"nodes": body.nodes},
        last_seen=now_ms(),
        runtime_info=runtime.model_dump(exclude={"failure", "checking"}) if runtime else None,
    )
    pending = _active_update(machine)
    if not pending:
        return
    if (
        runtime
        and pending.release
        and runtime.version == pending.release.version
        and runtime.build == pending.release.build
    ):
        pending.status = "succeeded"
    elif runtime and runtime.failure and runtime.failure.id == pending.id:
        pending.status = "failed"
        pending.error = runtime.failure.reason
    elif not runtime or not runtime.can_update:
        pending.status = "failed"
        pending.error = "当前启动方式无法继续更新"
    machine.update_info = pending.model_dump()


def request_update(
    db: Session, machine: Machine, release: WorkerRelease | None, sha256: str | None = None
) -> None:
    """请求工作机空闲后更新到最新版，重复请求沿用当前更新。"""
    write_lock(db, Machine, machine.id)
    db.refresh(machine)
    if machine.revoked_at:
        raise HTTPException(409, "工作机已撤销")
    if _active_update(machine):
        return
    if sha256 is not None and (release is None or release.sha256 != sha256):
        raise HTTPException(409, "可用版本已变更，请刷新后再更新")
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    if not _has_update(runtime, release):
        raise HTTPException(409, "这台工作机没有可用的更新")
    _queue_update(machine)


def start_update(
    db: Session, machine: Machine, update_id: str, settings: Settings
) -> WorkerRelease:
    """工作机交还任务后，读取当时可用的最新签名发布包。"""
    _connection_update(db, machine, last_seen=now_ms())
    pending = _active_update(machine)
    if not pending or pending.id != update_id:
        raise HTTPException(409, "更新请求已失效")
    if machine.busy_until > now_ms():
        raise HTTPException(409, "请在当前任务结束后更新")
    published = published_worker(settings)
    runtime = WorkerRuntime.model_validate(machine.runtime_info) if machine.runtime_info else None
    if published is None or not _has_update(runtime, published.release):
        raise HTTPException(409, "这台工作机没有可用的更新")
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
        raise HTTPException(404, "更新包不存在")

    published = published_worker(settings)
    if published and published.release.sha256 == sha256:
        try:
            return worker_archive_bytes(settings, pending.release)
        except FileNotFoundError:
            published = published_worker(settings)
        except (OSError, ValueError):
            raise HTTPException(503, "工作机更新包校验或读取失败") from None
    if published is None or published.release.sha256 == sha256:
        raise HTTPException(503, "工作机更新包暂不可用")
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
    if not machine or machine.revoked_at:
        raise _invalid_key()
    return machine


CurrentMachine = Annotated[Machine, Depends(authenticate_machine)]
# 工作机 API Key 识别机器，任务操作还需提供对应领取产生的租约凭据。
Lease = Annotated[str | None, Header(alias="X-Task-Lease")]


def expire_leases(db: Session) -> None:
    """结束租约过期的任务。清单齐全时补记成功，其余标记失败并保留成功的执行。

    先用只读查询按索引找出到期任务，没有到期任务时不写入，也就不取得写锁。
    """
    # An ambiguous GPU run must never be automatically submitted a second time.
    now = now_ms()
    expired = (Task.status == Status.RUNNING, Task.lease_expires_at <= now)
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


# 用户停止任务后，工作机凭这段说明区分「被停止」和「租约过期」。工作机包里有同名常量。
TASK_CANCELLED = "任务已取消"


def fence(
    db: Session, task_id: str, machine: Machine, lease: str | None, *, terminal: bool = False
) -> Task:
    """返回当前工作机可操作的任务。`lease` 是原始租约凭据，平台仅保存其摘要。

    身份或任务归属不匹配返回 404，凭据无效、租约已过期或任务已被用户停止返回 409。
    `terminal=True` 时允许使用原凭据确认已成功或失败的任务。
    """
    task = db.get(Task, task_id, populate_existing=True)
    if not task or task.machine_id != machine.id or task.owner_id != machine.owner_id:
        raise HTTPException(404, "任务不存在")
    if not lease or not secrets.compare_digest(task.lease_hash or "", digest(lease)):
        raise HTTPException(409, "任务租约无效")
    if terminal and task.status in {Status.SUCCEEDED, Status.FAILED}:
        return task
    if task.status == Status.CANCELLED:
        raise HTTPException(409, TASK_CANCELLED)
    if task.status != Status.RUNNING or (task.lease_expires_at or 0) <= now_ms():
        raise HTTPException(409, "任务租约已失效")
    return task


def claim_task(
    db: Session, machine: Machine, claim_id: str, secret: str, lease_seconds: int
) -> tuple[Task | None, bool]:
    """为空闲的工作机领取最早排队的任务，返回任务及是否为新领取。

    `claim_id` 与 `secret` 由工作机先持久化，重试同一次领取返回原任务。机器繁忙或
    没有可领任务时返回 `(None, False)`。新领取的占用和租约由调用方提交。
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
    task_id = db.scalar(
        select(Task.id)
        .where(
            Task.machine_id == machine.id,
            Task.owner_id == machine.owner_id,
            Task.status == Status.QUEUED,
        )
        .order_by(Task.created_at, Task.id)
        .limit(1)
    )
    if not task_id:
        db.rollback()
        return None, False
    updated = db.execute(
        update(Task)
        .where(Task.id == task_id, Task.status == Status.QUEUED)
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
        raise HTTPException(404, "任务不存在")
    return task, True


def lock_leased_task(db: Session, task_id: str, machine: Machine, lease: str | None) -> Task:
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
    status: Literal["succeeded", "failed"],
    error: str | None = None,
) -> None:
    now = now_ms()
    task.status = status
    task.stage = status
    task.error = error
    task.updated_at = now
    if status == Status.SUCCEEDED:
        task.progress = 100
    else:
        fail_unfinished_executions(db, task.id, status)
    # 释放与本任务租约对应的占用，避免结束旧任务时清掉新任务已取得的占用。
    db.execute(
        update(Machine)
        .where(Machine.id == task.machine_id, Machine.busy_until == task.lease_expires_at)
        .values(busy_until=0, last_seen=now)
    )
