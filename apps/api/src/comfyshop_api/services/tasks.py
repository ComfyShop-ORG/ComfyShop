"""任务的读取、归属校验和提交。领取与状态写入见 `services.machines`。"""

import json

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    MediaObject,
    Artifact,
    Execution,
    Machine,
    Status,
    Task,
    TaskAsset,
    User,
    UserPreference,
    now_ms,
)
from comfyshop_api.schemas import MediaRead, TaskCreate, TaskRead
from comfyshop_api.security import digest
from comfyshop_api.services.executions import (
    create_executions,
    fail_unfinished_executions,
    owned_execution,
)
from comfyshop_api.services.assets import ensure_quota_for_restore, ensure_quota_for_reuse
from comfyshop_api.services.inputs import compile_inputs
from comfyshop_api.services.media_records import artifact_media
from comfyshop_api.services.workflows import readable_version, readable_workflow
from comfyshop_api.services.works import readable_work


def task_covers(db: Session, tasks: list[Task]) -> dict[str, MediaRead]:
    """按任务 ID 返回列表封面：最早一次有成品的执行里的首张图片，没有图片时取首个视频。"""
    if not tasks:
        return {}
    cover = (
        select(Artifact.id)
        .join(Execution, Execution.id == Artifact.execution_id)
        .join(Artifact.media)
        .where(
            Execution.task_id == Task.id,
            Execution.status == Status.SUCCEEDED,
            Artifact.visible(),
        )
        .order_by(
            Execution.index,
            MediaObject.content_type.startswith("image/").desc(),
            Artifact.output_index,
            Artifact.id,
        )
        .limit(1)
        .correlate(Task)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Task.id, Artifact)
        .join(Artifact, Artifact.id == cover)
        .where(Task.id.in_([task.id for task in tasks]))
    ).tuples()
    return {task_id: artifact_media(artifact) for task_id, artifact in rows}


def task_read(task: Task, media: MediaRead | None = None) -> TaskRead:
    return TaskRead(
        id=task.id,
        workflow_id=task.workflow_id,
        version_id=task.version_id,
        workflow_name=task.workflow_name,
        execution_count=task.execution_count,
        status=task.status,
        progress=task.progress,
        machine_id=task.machine_id,
        stage=task.stage,
        error=task.error,
        prompt_id=task.prompt_id,
        started=task.created_at,
        updated=task.updated_at,
        input_values=task.input_values,
        source_execution_id=task.source_execution_id,
        source_work_id=task.source_work_id,
        media=media,
    )


def owned_task(db: Session, task_id: str, user_id: str, *, include_deleted: bool = False) -> Task:
    """按任务 ID 和所有者读取任务。默认只读取未删除的任务记录。"""
    task = db.get(Task, task_id)
    if (
        not task
        or task.owner_id != user_id
        or (task.deleted_at is not None and not include_deleted)
    ):
        raise HTTPException(404, "任务不存在")
    return task


def _submitted_before(db: Session, user_id: str, key: str, request_hash: str) -> Task | None:
    """返回同一幂等键已受理的任务。参数不同或记录已删除返回 HTTP 409。"""
    prior = db.scalar(select(Task).where(Task.owner_id == user_id, Task.idempotency_key == key))
    if prior is None:
        return None
    if prior.request_hash != request_hash:
        raise HTTPException(409, "重复请求的参数不一致")
    if prior.deleted_at is not None:
        raise HTTPException(409, "任务记录已删除")
    return prior


def submit_task(db: Session, user: User, body: TaskCreate, asset_quota: int) -> tuple[Task, bool]:
    """校验版本、重跑来源、工作机和输入后写入排队任务，返回任务及是否新建。

    同一账号重复提交相同幂等键和参数时返回原任务。参数冲突或没有可用工作机返回
    HTTP 409，重跑来源与版本不匹配或图不是 API 格式返回 422。
    """
    request_hash = digest(
        json.dumps(
            body.model_dump(
                exclude={"idempotency_key"}
                | {
                    field
                    for field in ["source_execution_id", "source_work_id"]
                    if getattr(body, field) is None
                }
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    prior = _submitted_before(db, user.id, body.idempotency_key, request_hash)
    if prior:
        return prior, False
    workflow = readable_workflow(db, body.workflow_id, user.id)
    version = readable_version(db, workflow, body.version_id, user.id)
    if body.source_work_id and body.source_execution_id:
        raise HTTPException(422, "只能指定一个重跑来源")
    if body.source_execution_id:
        _, source_task = owned_execution(db, body.source_execution_id, user.id)
        if source_task.workflow_id != workflow.id or source_task.version_id != version.id:
            raise HTTPException(422, "重跑来源与工作流版本不匹配")
    if body.source_work_id:
        source = readable_work(db, body.source_work_id, user.id)
        if source.workflow_id != workflow.id or source.version_id != version.id:
            raise HTTPException(422, "重跑来源与工作流版本不匹配")
    if version.format != "api":
        raise HTTPException(422, "请从 ComfyUI 导出 API 格式的工作流")
    pref = db.get(UserPreference, user.id)
    machine_id = body.machine_id or (pref.default_machine_id if pref else None)
    machine = db.get(Machine, machine_id) if machine_id else None
    if not machine or machine.owner_id != user.id or machine.revoked_at:
        raise HTTPException(409, "请选择可用的工作机")
    input_graph, input_values, input_schema, assets = compile_inputs(
        db, version, machine, body.input_values, body.input_schema_hash
    )
    # 引用已释放的素材会让它重新计入配额。
    ensure_quota_for_reuse(db, user.id, [asset.asset_id for asset in assets], asset_quota)
    task = Task(
        owner_id=user.id,
        workflow_id=workflow.id,
        version_id=version.id,
        workflow_name=workflow.name,
        execution_count=body.execution_count,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
        machine_id=machine.id,
        input_graph=input_graph,
        input_values=input_values,
        input_schema=input_schema,
        source_execution_id=body.source_execution_id,
        source_work_id=body.source_work_id,
    )
    db.add(task)
    try:
        # 任务、各次执行的快照和素材绑定在同一事务内写入。
        db.flush()
        create_executions(db, task)
        for asset in assets:
            asset.task_id = task.id
            db.add(asset)
        db.commit()
    except IntegrityError:
        # 并发的同键提交由唯一约束拦下，按已受理的那一条应答。
        db.rollback()
        prior = _submitted_before(db, user.id, body.idempotency_key, request_hash)
        if prior is None:
            # 没有同键任务时冲突来自引用：所选素材或来源在校验之后被删除了。
            raise HTTPException(409, "所选素材或来源已不可用，请重新选择后提交") from None
        return prior, False
    return task, True


def cancel_task(db: Session, task: Task) -> None:
    """取消排队任务或停止执行中的任务，释放这次领取对工作机的占用，由调用方提交。

    先取得任务写锁再读取状态和租约，与工作机的领取、续期和完成串行，释放占用时用的是
    最新的租约时间。任务已经结束返回 409。
    """
    write_lock(db, Task, task.id)
    db.refresh(task)
    if task.status == Status.CANCELLED:
        return
    if task.status not in Status.ACTIVE:
        raise HTTPException(409, "任务已经结束，不能取消")
    stamp = now_ms()
    lease_expires_at = task.lease_expires_at
    task.status = Status.CANCELLED
    task.stage = Status.CANCELLED
    task.updated_at = stamp
    fail_unfinished_executions(db, task.id, Status.CANCELLED)
    if lease_expires_at is not None and task.machine_id:
        db.execute(
            update(Machine)
            .where(Machine.id == task.machine_id, Machine.busy_until == lease_expires_at)
            .values(busy_until=0)
        )


def resume_task(db: Session, task: Task) -> None:
    """撤销对未领取任务的取消，任务回到队列原来的位置，由调用方提交。

    工作机领取过的任务不能恢复，避免同一次提交在 GPU 上执行两遍；已删除的记录也不能恢复
    排队。其他情况返回 409。
    """
    write_lock(db, Task, task.id)
    db.refresh(task)
    if task.status != Status.CANCELLED or task.claim_id is not None or task.deleted_at:
        raise HTTPException(409, "只有未开始执行就取消的任务可以恢复排队")
    # 取消之后工作机可能已被撤销，素材也可能过了保留期被清理，这样的任务回到队列也执行不了。
    machine = db.get(Machine, task.machine_id) if task.machine_id else None
    if machine is None or machine.revoked_at is not None:
        raise HTTPException(409, "任务的工作机已撤销，请重新选择工作机后提交")
    wanted = {
        value["assetId"]
        for value in task.input_values.values()
        if isinstance(value, dict) and "assetId" in value
    }
    bound = set(db.scalars(select(TaskAsset.asset_id).where(TaskAsset.task_id == task.id)))
    if wanted - bound:
        raise HTTPException(409, "任务引用的素材已清理，请重新上传后提交")
    stamp = now_ms()
    task.status = Status.QUEUED
    task.stage = "queued"
    task.updated_at = stamp
    db.execute(
        update(Execution)
        .where(Execution.task_id == task.id, Execution.status == Status.CANCELLED)
        .values(status=Status.QUEUED, updated_at=stamp)
    )


def delete_task(db: Session, task: Task) -> None:
    """从历史隐藏已结束的任务，由调用方提交。在写锁内确认状态，不会隐藏刚恢复排队的任务。"""
    write_lock(db, Task, task.id)
    db.refresh(task)
    if task.status in Status.ACTIVE:
        raise HTTPException(409, "只能删除已结束的任务记录")
    task.mark_deleted()


def restore_task(db: Session, task: Task, asset_quota: int) -> None:
    """撤销删除任务记录，由调用方提交。

    删除时释放的素材随任务重新计入配额，放回后超出 `asset_quota` 返回 413。
    """
    ensure_quota_for_restore(db, task.owner_id, task.id, asset_quota)
    db.refresh(task)
    task.restore()
