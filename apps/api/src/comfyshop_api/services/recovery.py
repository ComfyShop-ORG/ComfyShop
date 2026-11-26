"""为原工作机核对已经结束的执行，并授权有时限的成品补传。"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import Artifact, Execution, Machine, Status, Task, now_ms
from comfyshop_api.schemas import WorkerRecovery, WorkerRecoveryRead
from comfyshop_api.services.executions import execution_at
from comfyshop_api.services.machines import claimed_task, expire_leases


def recovery_execution(
    db: Session,
    task_id: str,
    index: int,
    machine: Machine,
    lease: str | None,
    window: int,
    *,
    lock: bool,
    uploading: bool = True,
) -> tuple[Task, Execution]:
    task = claimed_task(db, task_id, machine, lease)
    if lock:
        write_lock(db, Task, task.id)
        task = claimed_task(db, task_id, machine, lease)
    execution = execution_at(db, task, index)
    if task.status in Status.ACTIVE or task.deleted_at is not None or execution.retry_task_id:
        raise HTTPException(409, msg("execution.recoveryUnavailable"))
    if execution.status == Status.SUCCEEDED:
        return task, execution
    if (
        execution.status not in {Status.FAILED, Status.CANCELLED}
        or execution.updated_at <= now_ms() - window * 1000
        or (uploading and execution.recovery_status != "uploading")
    ):
        raise HTTPException(409, msg("execution.recoveryUnavailable"))
    return task, execution


def prepare_recovery(
    db: Session,
    task_id: str,
    index: int,
    body: WorkerRecovery,
    machine: Machine,
    lease: str | None,
    window: int,
) -> WorkerRecoveryRead:
    task = claimed_task(db, task_id, machine, lease)
    if task.status == Status.RUNNING and (task.lease_expires_at or 0) <= now_ms():
        expire_leases(db)
    _, execution = recovery_execution(
        db, task_id, index, machine, lease, window, lock=True, uploading=False
    )
    if execution.prompt_id != body.prompt_id:
        raise HTTPException(409, msg("media.thisRunIsAlreadyAssociatedWith"))
    if execution.status == Status.SUCCEEDED:
        return WorkerRecoveryRead(action="done")
    if body.outcome == "missing":
        execution.recovery_status = "rerunnable"
        return WorkerRecoveryRead(action="done")
    execution.recovery_status = "uploading"
    confirmed = db.scalars(
        select(Artifact.client_id).where(Artifact.execution_id == execution.id, Artifact.visible())
    ).all()
    return WorkerRecoveryRead(action="upload", client_ids=list(confirmed))
