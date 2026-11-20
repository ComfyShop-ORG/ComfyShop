"""网页任务接口，负责提交、查询、取消和删除记录。领取与状态写入见 `api.worker`。"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select, tuple_

from comfyshop_api.models import (
    Status,
    Asset,
    Execution,
    Machine,
    Task,
    TaskAsset,
    WorkflowVersion,
    now_ms,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ActiveTaskRead,
    ExecutionState,
    GraphRead,
    RecordedInput,
    TaskActivity,
    TaskCreate,
    TaskInputsRead,
    TaskPage,
    TaskProgressRead,
    TaskRead,
    TaskWaitReason,
)
from comfyshop_api.security import Config, CurrentUser, DB, Writer
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.machines import machine_is_online
from comfyshop_api.services import tasks as task_service
from comfyshop_api.services.tasks import owned_task, submit_task, task_covers, task_read

router = APIRouter(prefix="/tasks", tags=["tasks"])


# `body` 指定版本、表单快照哈希和输入值，可选择覆盖默认工作机。新任务排队并返回 201。
# 同一账号重复提交相同幂等键和参数时返回原任务（200），参数冲突时返回 409。
@router.post("", response_model=TaskRead, status_code=201, responses={200: {"model": TaskRead}})
def create_task(
    body: TaskCreate, response: Response, db: DB, user: Writer, config: Config
) -> TaskRead:
    task, created = submit_task(db, user, body, config.asset_quota_bytes)
    if not created:
        response.status_code = 200
    return task_read(task)


# state 筛选任务：active 为排队或执行中，其余对应同名的结束状态。不传时返回全部。
@router.get("", response_model=TaskPage)
def list_tasks(
    db: DB,
    user: CurrentUser,
    workflow_id: str | None = None,
    state: Literal["active", "succeeded", "failed", "cancelled"] | None = None,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
) -> TaskPage:
    query = select(Task).where(Task.owner_id == user.id, Task.visible())
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if state:
        query = query.where(Task.status.in_(Status.ACTIVE if state == "active" else (state,)))
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(Task.created_at, Task.id) < tuple(position))
    records = db.scalars(
        query.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(records, limit, lambda task: (task.created_at, task.id))
    covers = task_covers(db, list(items))
    return TaskPage(
        items=[task_read(item, covers.get(item.id)) for item in items], next_cursor=next_cursor
    )


@router.get("/activity", response_model=TaskActivity)
def task_activity(
    db: DB, user: CurrentUser, workflow_id: str | None = None, task_id: str | None = None
) -> TaskActivity:
    filters = [Task.owner_id == user.id]
    if workflow_id:
        filters.append(Task.workflow_id == workflow_id)
    if task_id:
        filters.append(Task.id == task_id)
    active = db.execute(
        select(Task.id, Task.status, Task.progress, Task.stage, Task.updated_at.label("updated"))
        .where(*filters, Task.status.in_(Status.ACTIVE))
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    completed = db.scalar(
        select(func.count(Execution.id))
        .join(Task, Task.id == Execution.task_id)
        .where(*filters, Execution.status == Status.SUCCEEDED)
    )
    return TaskActivity(
        active_tasks=[ActiveTaskRead.model_validate(record) for record in active],
        completed_executions=completed or 0,
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, db: DB, user: CurrentUser) -> TaskRead:
    # 与列表一样带上代表成品，列表里刚结束的任务按 ID 刷新后也能显示结果。
    task = owned_task(db, task_id, user.id)
    return task_read(task, task_covers(db, [task]).get(task.id))


@router.get("/{task_id}/progress", response_model=TaskProgressRead)
def task_progress(task_id: str, db: DB, user: CurrentUser) -> TaskProgressRead:
    # 一次只读查询取得任务、工作机和执行状态，详情页轮询时使用同一份快照。
    rows = db.execute(
        select(
            Task.status,
            Task.progress,
            Task.stage,
            Task.error,
            Task.updated_at,
            Machine.name.label("machine_name"),
            Machine.last_seen,
            Machine.revoked_at,
            Machine.busy_until,
            Execution.id.label("execution_id"),
            Execution.index.label("execution_index"),
            Execution.status.label("execution_status"),
        )
        .select_from(Task)
        .outerjoin(Machine, (Machine.id == Task.machine_id) & (Machine.owner_id == user.id))
        .outerjoin(Execution, Execution.task_id == Task.id)
        .where(Task.id == task_id, Task.owner_id == user.id, Task.visible())
        .order_by(Execution.index)
    ).all()
    if not rows:
        raise HTTPException(404, "任务不存在")
    snapshot = rows[0]
    wait_reason: TaskWaitReason | None = None
    if snapshot.status == Status.QUEUED:
        now = now_ms()
        if snapshot.machine_name is None:
            wait_reason = "machine_unassigned"
        elif not machine_is_online(snapshot.last_seen, snapshot.revoked_at, now):
            wait_reason = "machine_offline"
        elif snapshot.busy_until is not None and snapshot.busy_until > now:
            wait_reason = "machine_busy"
    return TaskProgressRead(
        status=snapshot.status,
        progress=snapshot.progress,
        stage=snapshot.stage,
        error=snapshot.error,
        updated=snapshot.updated_at,
        machine_name=snapshot.machine_name,
        wait_reason=wait_reason,
        executions=[
            ExecutionState(
                id=row.execution_id, index=row.execution_index, status=row.execution_status
            )
            for row in rows
            if row.execution_id is not None
        ],
    )


@router.get("/{task_id}/inputs", response_model=TaskInputsRead)
def task_inputs(task_id: str, db: DB, user: CurrentUser) -> TaskInputsRead:
    # 执行结果的生成参数仍使用来源任务的输入定义和素材。
    task = owned_task(db, task_id, user.id, include_deleted=True)
    version = db.scalar(select(WorkflowVersion.number).where(WorkflowVersion.id == task.version_id))
    if version is None:
        raise HTTPException(404, "工作流版本不存在")
    assets = db.scalars(
        select(Asset)
        .join(TaskAsset, TaskAsset.asset_id == Asset.id)
        .where(TaskAsset.task_id == task.id, Asset.owner_id == user.id)
        .distinct()
    )
    return TaskInputsRead(
        version=version,
        fields=[
            RecordedInput(
                id=field["id"],
                label=field["label"],
                node_id=field["node_id"],
                node_title=field["node_title"],
                input_name=field["input_name"],
            )
            for field in task.input_schema.get("fields", [])
        ],
        assets=[asset_read(asset) for asset in assets],
    )


# 取消排队中的任务，或停止执行中的任务。已完整回传的执行保留为成功结果，
# 工作机在下一次心跳或回传时得知任务已停止。
@router.post("/{task_id}/cancel", response_model=TaskRead)
def cancel_task(task_id: str, db: DB, user: Writer) -> TaskRead:
    task = owned_task(db, task_id, user.id)
    task_service.cancel_task(db, task)
    db.commit()
    return task_read(task)


# 撤销对排队任务的取消，任务回到队列原来的位置。
@router.post("/{task_id}/resume", response_model=TaskRead)
def resume_task(task_id: str, db: DB, user: Writer) -> TaskRead:
    task = owned_task(db, task_id, user.id)
    task_service.resume_task(db, task)
    db.commit()
    return task_read(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: DB, user: Writer) -> Response:
    task = owned_task(db, task_id, user.id, include_deleted=True)
    task_service.delete_task(db, task)
    db.commit()
    return Response(status_code=204)


@router.post("/{task_id}/restore", status_code=204)
def restore_task(task_id: str, db: DB, user: Writer, config: Config) -> Response:
    task = owned_task(db, task_id, user.id, include_deleted=True)
    task_service.restore_task(db, task, config.asset_quota_bytes)
    db.commit()
    return Response(status_code=204)


@router.get("/{task_id}/graph", response_model=GraphRead)
def get_task_graph(task_id: str, db: DB, user: CurrentUser) -> GraphRead:
    task = owned_task(db, task_id, user.id)
    version = db.get(WorkflowVersion, task.version_id)
    if version is None:
        raise HTTPException(404, "工作流版本不存在")
    return GraphRead(version_id=version.id, graph=version.graph)
