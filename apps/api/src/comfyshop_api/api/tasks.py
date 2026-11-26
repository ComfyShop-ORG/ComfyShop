"""网页任务接口，负责提交、查询、取消和删除记录。领取与状态写入见 `api.worker`。"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select, tuple_

from comfyshop_api.api.teams import TeamEditor, TeamReader
from comfyshop_api.api.workspace_shares import SignedInWorkspaceReader
from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.models import (
    Asset,
    Execution,
    Status,
    Task,
    TaskAsset,
    TeamRole,
    WorkflowVersion,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ActiveTaskRead,
    CostEstimate,
    ErrorRead,
    GenerationInputs,
    GraphRead,
    ServiceRetryRequest,
    TaskActivity,
    TaskCreate,
    TaskInputsRead,
    TaskMachineChange,
    TaskPage,
    TaskProgressRead,
    TaskProjectChange,
    TaskRead,
    TaskRetryRequest,
)
from comfyshop_api.security import DB, Config, CurrentUser, LockedWriter, Writer, workspace_records
from comfyshop_api.services import tasks as task_service
from comfyshop_api.services.assets import asset_scope
from comfyshop_api.services.connections import cancel_remote
from comfyshop_api.services.cost_estimates import estimate_cost
from comfyshop_api.services.executions import task_has_results
from comfyshop_api.services.inputs import recorded_input
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.projects import scoped_project
from comfyshop_api.services.result_comparisons import output_comparisons
from comfyshop_api.services.tasks import owned_task, submit_task, task_covers, task_read
from comfyshop_api.services.teams import TeamAccess

router = APIRouter(prefix="/tasks", tags=["tasks"])


def managed_task(
    db: DB,
    task_id: str,
    user_id: str,
    team: TeamAccess | None,
    *,
    allow_submitter: bool = False,
    include_deleted: bool = False,
) -> Task:
    task = owned_task(
        db,
        task_id,
        user_id,
        team_id=team.team.id if team else None,
        include_deleted=include_deleted,
    )
    if team and not (
        team.role.permits(TeamRole.MANAGER) or (allow_submitter and task.owner_id == user_id)
    ):
        raise HTTPException(403, msg("team.permissionDenied"))
    return task


# `body` 指定版本、表单快照哈希和输入值，可选择覆盖默认工作机。新任务排队并返回 201。
# 同一账号重复提交相同幂等键和参数时返回原任务（200），参数冲突时返回 409。
@router.post(
    "",
    status_code=201,
    responses={200: {"model": TaskRead}},
)
def create_task(
    body: TaskCreate,
    response: Response,
    db: DB,
    user: LockedWriter,
    team: TeamEditor,
    config: Config,
    language: Language,
) -> TaskRead:
    task, created = submit_task(db, user, body, config, language, team=team)
    if not created:
        response.status_code = 200
    return task_read(task, language=language)


@router.post("/cost-estimate", responses={503: {"model": ErrorRead}})
def estimate_task_cost(
    body: GenerationInputs,
    db: DB,
    user: Writer,
    team: TeamReader,
    config: Config,
    language: Language,
) -> CostEstimate:
    return estimate_cost(db, body, user.id, team, config, language)


# state 筛选任务：active 为排队或执行中，其余对应同名的结束状态。不传时返回全部。
@router.get("")
def list_tasks(
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    language: Language,
    workflow_id: str | None = None,
    version_id: str | None = None,
    project_id: UUID | None = None,
    state: Literal["active", Status.SUCCEEDED, Status.FAILED, Status.CANCELLED] | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> TaskPage:
    query = select(Task).where(
        workspace_records(Task.owner_id, Task.team_id, owner_id, team.team.id if team else None),
        Task.visible(),
    )
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if version_id:
        query = query.where(Task.version_id == version_id)
    if project_id:
        project = scoped_project(db, str(project_id), owner_id, team.team.id if team else None)
        query = query.where(Task.project_id == project.id)
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
        items=[task_read(item, covers.get(item.id), language=language) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/activity")
def task_activity(
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    workflow_id: str | None = None,
    version_id: str | None = None,
    task_id: str | None = None,
    project_id: UUID | None = None,
) -> TaskActivity:
    team_id = team.team.id if team else None
    filters = [workspace_records(Task.owner_id, Task.team_id, owner_id, team_id)]
    if workflow_id:
        filters.append(Task.workflow_id == workflow_id)
    if version_id:
        filters.append(Task.version_id == version_id)
    if task_id:
        filters.append(Task.id == task_id)
    if project_id:
        project = scoped_project(db, str(project_id), owner_id, team_id)
        filters.append(Task.project_id == project.id)
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


@router.get("/{task_id}")
def get_task(
    task_id: str, db: DB, team: TeamReader, owner_id: SignedInWorkspaceReader, language: Language
) -> TaskRead:
    # 与列表一样带上代表成品，列表里刚结束的任务按 ID 刷新后也能显示结果。
    task = owned_task(db, task_id, owner_id, team_id=team.team.id if team else None)
    return task_read(task, task_covers(db, [task]).get(task.id), language=language)


@router.get("/{task_id}/progress")
def task_progress(
    task_id: str,
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    language: Language,
    config: Config,
    include_takeover_history: bool = False,
) -> TaskProgressRead:
    return task_service.task_progress(
        db,
        task_id,
        owner_id,
        language,
        config.failed_artifact_ttl_seconds,
        include_takeover_history=include_takeover_history,
        team_id=team.team.id if team else None,
    )


@router.put("/{task_id}/machine")
def change_task_machine(
    task_id: str,
    body: TaskMachineChange,
    db: DB,
    user: LockedWriter,
    team: TeamEditor,
    language: Language,
) -> TaskRead:
    task = managed_task(db, task_id, user.id, team)
    task_service.change_task_machine(db, task, body.machine_id, language)
    if team:
        team.record(db, "task.machineChanged", task.id)
    db.commit()
    return task_read(task, language=language)


@router.put("/{task_id}/project", status_code=204)
def change_task_project(
    task_id: str, body: TaskProjectChange, db: DB, user: CurrentUser, team: TeamEditor
) -> None:
    task = managed_task(db, task_id, user.id, team, allow_submitter=True, include_deleted=True)
    if task.deleted_at is not None and not db.scalar(select(task_has_results(task.id))):
        raise HTTPException(404, msg("task.notFound"))
    task_service.assign_project(db, task, str(body.project_id) if body.project_id else None, team)


@router.post("/{task_id}/retry-executions", status_code=201, responses={200: {"model": TaskRead}})
def retry_executions(
    task_id: str,
    body: TaskRetryRequest | ServiceRetryRequest,
    response: Response,
    db: DB,
    user: LockedWriter,
    team: TeamEditor,
    language: Language,
) -> TaskRead:
    source = managed_task(db, task_id, user.id, team)
    task, created = task_service.retry_executions(db, source, body, language, team=team)
    if not created:
        response.status_code = 200
    return task_read(task, language=language)


@router.get("/{task_id}/inputs")
def task_inputs(
    task_id: str,
    db: DB,
    user: CurrentUser,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    language: Language,
) -> TaskInputsRead:
    # 执行结果的生成参数仍使用来源任务的输入定义和素材。
    team_id = team.team.id if team else None
    task = owned_task(db, task_id, owner_id, team_id=team_id, include_deleted=True)
    if (
        task.deleted_at is not None
        and (team is not None or owner_id != user.id)
        and not db.scalar(select(task_has_results(task.id)))
    ):
        raise HTTPException(404, msg("task.notFound"))
    version = db.scalar(select(WorkflowVersion.number).where(WorkflowVersion.id == task.version_id))
    if version is None:
        raise HTTPException(404, msg("workflow.versionNotFound"))
    assets = db.scalars(
        select(Asset)
        .join(TaskAsset, TaskAsset.asset_id == Asset.id)
        .where(TaskAsset.task_id == task.id, asset_scope(owner_id, team_id))
        .distinct()
    )
    readable_assets = [asset_read(asset) for asset in assets]
    return TaskInputsRead(
        version=version,
        fields=[recorded_input(field, language) for field in task.input_schema.get("fields", [])],
        assets=readable_assets,
        comparisons=output_comparisons(task.input_graph, readable_assets)
        if readable_assets
        else {},
    )


# 取消排队中的任务，或停止执行中的任务。已完整回传的执行保留为成功结果，
# 工作机在下一次心跳或回传时得知任务已停止。
@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str, db: DB, user: LockedWriter, team: TeamEditor, language: Language, config: Config
) -> TaskRead:
    task = managed_task(db, task_id, user.id, team, allow_submitter=True)
    changed = task.status != Status.CANCELLED
    task_service.cancel_task(db, task)
    if team and changed:
        team.record(db, "task.cancelled", task.id)
    await cancel_remote(db, task, config)
    return task_read(task, language=language)


# 撤销对排队任务的取消，任务回到队列原来的位置。
@router.post("/{task_id}/resume")
def resume_task(
    task_id: str, db: DB, user: LockedWriter, team: TeamEditor, language: Language
) -> TaskRead:
    task = managed_task(db, task_id, user.id, team, allow_submitter=True)
    task_service.resume_task(db, task)
    if team:
        team.record(db, "task.resumed", task.id)
    db.commit()
    return task_read(task, language=language)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: DB, user: LockedWriter, team: TeamEditor) -> Response:
    task = managed_task(db, task_id, user.id, team, include_deleted=True)
    changed = task.deleted_at is None
    task_service.delete_task(db, task)
    if team and changed:
        team.record(db, "task.deleted", task.id)
    db.commit()
    return Response(status_code=204)


@router.post("/{task_id}/restore", status_code=204)
def restore_task(
    task_id: str, db: DB, user: LockedWriter, team: TeamEditor, config: Config
) -> Response:
    task = managed_task(db, task_id, user.id, team, include_deleted=True)
    changed = task.deleted_at is not None
    task_service.restore_task(db, task, config)
    if team and changed:
        team.record(db, "task.restored", task.id)
    db.commit()
    return Response(status_code=204)


@router.get("/{task_id}/graph")
def get_task_graph(task_id: str, db: DB, user: CurrentUser, team: TeamReader) -> GraphRead:
    task = owned_task(db, task_id, user.id, team_id=team.team.id if team else None)
    version = db.get(WorkflowVersion, task.version_id)
    if version is None:
        raise HTTPException(404, msg("workflow.versionNotFound"))
    return GraphRead(version_id=version.id, graph=version.graph)
