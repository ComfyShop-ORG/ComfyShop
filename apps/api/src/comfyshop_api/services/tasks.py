"""任务的读取、归属校验和提交。领取与状态写入见 `services.machines`。"""

import json

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import SOURCE_LANGUAGE, localize_task_error, msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Artifact,
    Execution,
    Machine,
    OfficialTakeoverWait,
    OfficialWorkerPoll,
    Status,
    Task,
    TaskAsset,
    User,
    Work,
    Workflow,
    WorkflowVersion,
    now_ms,
)
from comfyshop_api.schemas import (
    AssetReference,
    ExecutionState,
    GenerationInputs,
    MediaRead,
    ServiceRetryRequest,
    TakeoverHistoryRead,
    TakeoverWaitRead,
    TaskCreate,
    TaskProgressRead,
    TaskRead,
    TaskRetryRequest,
    TaskWaitReason,
)
from comfyshop_api.security import digest, owned_record, workspace_records
from comfyshop_api.services.assets import ensure_quota_for_restore, ensure_quota_for_reuse
from comfyshop_api.services.connections import matched
from comfyshop_api.services.executions import (
    create_executions,
    fail_unfinished_executions,
    owned_execution,
)
from comfyshop_api.services.inputs import compile_inputs
from comfyshop_api.services.machines import (
    UPDATE_IN_PROGRESS,
    last_takeover_wait_number,
    machine_is_online,
    machine_preference,
    machine_scope,
    record_official_wait,
    service_task_claimable,
)
from comfyshop_api.services.media_records import artifact_media
from comfyshop_api.services.projects import active_project, active_project_id
from comfyshop_api.services.teams import TeamAccess
from comfyshop_api.services.worker_types import (
    OFFICIAL,
    WORKERS,
    personal_worker_kinds,
    route,
    worker_type,
)
from comfyshop_api.services.workflows import readable_version, readable_workflow
from comfyshop_api.services.works import readable_work, reuse_work_inputs


def task_covers(db: Session, tasks: list[Task]) -> dict[str, MediaRead]:
    """按任务 ID 返回列表封面：最早一次有成品的执行里的首张图片，没有图片时取首个视频。"""
    if not tasks:
        return {}
    cover = (
        select(Artifact.id)
        .join(Execution, Execution.id == Artifact.execution_id)
        .where(
            Execution.task_id == Task.id,
            Execution.status == Status.SUCCEEDED,
            Artifact.visible(),
        )
        .order_by(
            Execution.index,
            Artifact.content_type.startswith("image/").desc(),
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


def task_read(
    task: Task, media: MediaRead | None = None, *, language: str = SOURCE_LANGUAGE
) -> TaskRead:
    return TaskRead(
        id=task.id,
        owner=task.owner_id,
        workflow_id=task.workflow_id,
        version_id=task.version_id,
        workflow_name=task.workflow_name,
        execution_count=task.execution_count,
        status=task.status,
        progress=task.progress,
        machine_id=task.machine_id,
        machine_name=(task.worker_data or {}).get("connection_name") or task.machine_name,
        worker=route(task.worker_kind, (task.worker_data or {}).get("scope")),
        cloud_cancel=task.cloud_cancel,
        stage=task.stage,
        error=localize_task_error(task.error, language, official=task.worker_kind == OFFICIAL.kind),
        prompt_id=task.prompt_id,
        started=task.created_at,
        updated=task.updated_at,
        input_values=task.input_values,
        source_execution_id=task.source_execution_id,
        source_work_id=task.source_work_id,
        project_id=task.project_id,
        media=media,
    )


def owned_task(
    db: Session,
    task_id: str,
    user_id: str,
    *,
    team_id: str | None = None,
    include_deleted: bool = False,
) -> Task:
    """按所有者读取任务。恢复和历史结果可显式包含已删除任务。"""
    task = owned_record(db, Task, task_id, user_id, msg("task.notFound"), team_id=team_id)
    if task.deleted_at is not None and not include_deleted:
        raise HTTPException(404, msg("task.notFound"))
    return task


def _takeover_waits(
    db: Session, task_id: str, last_number: int, waiting_since: int | None, now: int
) -> list[TakeoverWaitRead]:
    """按进度快照的序号读取不可变的历史，并附上该快照中还在等待的一段。"""
    waits = []
    if last_number:
        records = db.execute(
            select(
                OfficialTakeoverWait.number,
                OfficialTakeoverWait.started_at,
                OfficialTakeoverWait.ended_at,
                (OfficialTakeoverWait.ended_at - OfficialTakeoverWait.started_at).label(
                    "duration_ms"
                ),
                OfficialTakeoverWait.outcome,
            )
            .where(
                OfficialTakeoverWait.task_id == task_id, OfficialTakeoverWait.number <= last_number
            )
            .order_by(OfficialTakeoverWait.number)
        )
        waits = [TakeoverWaitRead.model_validate(row) for row in records]
    if waiting_since is not None:
        waits.append(
            TakeoverWaitRead(
                number=last_number + 1,
                started_at=waiting_since,
                ended_at=None,
                duration_ms=now - waiting_since,
                outcome="waiting",
            )
        )
    return waits


def task_progress(
    db: Session,
    task_id: str,
    user_id: str,
    language: str,
    recovery_window_seconds: int,
    *,
    include_takeover_history: bool = False,
    team_id: str | None = None,
) -> TaskProgressRead:
    """在同一查询中读取任务、执行和按领取顺序计算的排队位置。"""
    now = now_ms()
    waiting = aliased(Task)
    earlier = tuple_(waiting.queued_at, waiting.id) < tuple_(Task.queued_at, Task.id)
    queued = Task.status == Status.QUEUED
    tracks = Task.worker_kind.in_([w.kind for w in WORKERS.values() if w.tracks_takeover])
    official_queued = queued & tracks
    official_running = (Task.status == Status.RUNNING) & tracks
    history_columns = (
        [
            Task.lease_expires_at,
            last_takeover_wait_number(Task.id)
            .correlate(Task)
            .scalar_subquery()
            .label("last_wait_number"),
        ]
        if include_takeover_history
        else []
    )
    adapter = Task.input_graph["adapter"].as_string()
    same_adapter = waiting.input_graph["adapter"].as_string() == adapter
    personal_ahead = (
        select(func.count())
        .where(
            waiting.machine_id == Task.machine_id,
            waiting.team_id.is_not_distinct_from(Task.team_id),
            or_(Task.team_id.is_not(None), waiting.owner_id == Task.owner_id),
            waiting.status == Status.QUEUED,
            waiting.visible(),
            earlier,
        )
        .correlate(Task)
        .scalar_subquery()
    )
    official_ahead = (
        select(func.count())
        .where(service_task_claimable(waiting, now, Task.worker_kind), same_adapter, earlier)
        .correlate(Task)
        .scalar_subquery()
    )
    official_busy = (
        select(waiting.id)
        .where(
            waiting.worker_kind == Task.worker_kind,
            waiting.visible(),
            same_adapter,
            waiting.status == Status.RUNNING,
            waiting.lease_expires_at > now,
        )
        .correlate(Task)
        .exists()
    )
    rows = db.execute(
        select(
            Task.status,
            Task.progress,
            Task.stage,
            Task.error,
            Task.updated_at,
            Task.claim_id,
            Task.worker_kind,
            Machine.id.label("machine_id"),
            func.coalesce(Task.worker_data["connection_name"].as_string(), Machine.name).label(
                "machine_name"
            ),
            Machine.last_seen,
            Machine.revoked_at,
            Machine.paused,
            Machine.busy_until,
            Machine.comfy_status,
            Machine.update_info["status"].as_string().label("update_status"),
            OfficialWorkerPoll.last_polled_at,
            case((official_queued, official_busy)).label("official_busy"),
            case(
                (official_queued, official_ahead),
                (
                    queued
                    & Task.worker_kind.in_(personal_worker_kinds())
                    & Machine.id.is_not(None),
                    personal_ahead,
                ),
            ).label("queue_ahead"),
            case(
                (official_running & (Task.lease_expires_at <= now), "waiting"),
                (
                    official_running & (Task.lease_expires_at > now) & Task.official_taken_over,
                    "resumed",
                ),
            ).label("official_takeover"),
            *history_columns,
            Execution.id.label("execution_id"),
            Execution.index.label("execution_index"),
            Execution.status.label("execution_status"),
            Execution.prompt_id.label("execution_prompt_id"),
            Execution.updated_at.label("execution_updated_at"),
            Execution.recovery_status,
            Execution.submission_pending,
            Execution.retry_task_id,
        )
        .select_from(Task)
        .outerjoin(Machine, (Machine.id == Task.machine_id) & machine_scope(user_id, team_id))
        .outerjoin(OfficialWorkerPoll, official_queued & (OfficialWorkerPoll.adapter == adapter))
        .outerjoin(Execution, Execution.task_id == Task.id)
        .where(
            Task.id == task_id,
            workspace_records(Task.owner_id, Task.team_id, user_id, team_id),
            Task.visible(),
        )
        .order_by(Execution.index)
    ).all()
    if not rows:
        raise HTTPException(404, msg("task.notFound"))
    snapshot = rows[0]
    ended = snapshot.status in (Status.FAILED, Status.CANCELLED) and snapshot.claim_id is not None
    cutoff = now - recovery_window_seconds * 1000
    wait_reason: TaskWaitReason | None = None
    if snapshot.status == Status.QUEUED:
        if worker_type(snapshot.worker_kind).tracks_takeover:
            if snapshot.official_busy:
                wait_reason = "official_busy"
            elif machine_is_online(snapshot.last_polled_at, None, now):
                wait_reason = "official_waiting"
            else:
                wait_reason = "official_no_recent_poll"
        elif worker_type(snapshot.worker_kind).service:
            wait_reason = "service_waiting"
        elif snapshot.machine_id is None:
            wait_reason = "machine_unassigned"
        elif not machine_is_online(snapshot.last_seen, snapshot.revoked_at, now):
            wait_reason = "machine_offline"
        elif snapshot.paused:
            wait_reason = "machine_paused"
        elif snapshot.update_status in UPDATE_IN_PROGRESS:
            wait_reason = "machine_updating"
        elif snapshot.comfy_status == "unreachable":
            wait_reason = "comfy_unreachable"
        elif snapshot.busy_until > now:
            wait_reason = "machine_busy"
        elif snapshot.comfy_status == "busy":
            wait_reason = "comfy_busy"
    executions = []
    for row in rows:
        if row.execution_id is None:
            continue
        recovery = None
        if ended and row.execution_status in (Status.FAILED, Status.CANCELLED):
            if row.retry_task_id:
                recovery = "scheduled"
            elif row.submission_pending:
                recovery = "unverified"
            elif row.recovery_status == "rerunnable" or row.execution_prompt_id is None:
                recovery = "rerunnable"
            elif worker_type(snapshot.worker_kind).service or row.execution_updated_at <= cutoff:
                recovery = "unverified"
            else:
                recovery = row.recovery_status or "pending"
        executions.append(
            ExecutionState(
                id=row.execution_id,
                index=row.execution_index,
                status=row.execution_status,
                recovery=recovery,
                retry_task_id=row.retry_task_id,
            )
        )
    history = None
    if include_takeover_history and worker_type(snapshot.worker_kind).tracks_takeover:
        waiting_since = (
            snapshot.lease_expires_at if snapshot.official_takeover == "waiting" else None
        )
        history = TakeoverHistoryRead(
            waits=_takeover_waits(db, task_id, snapshot.last_wait_number, waiting_since, now),
        )
    return TaskProgressRead(
        status=snapshot.status,
        progress=snapshot.progress,
        stage=snapshot.stage,
        error=localize_task_error(
            snapshot.error, language, official=worker_type(snapshot.worker_kind).tracks_takeover
        ),
        updated=snapshot.updated_at,
        machine_id=snapshot.machine_id,
        machine_name=snapshot.machine_name,
        wait_reason=wait_reason,
        queue_ahead=snapshot.queue_ahead,
        official_takeover=snapshot.official_takeover,
        takeover_history=history,
        executions=executions,
    )


def validate_frozen_machine(db: Session, task: Task, machine: Machine, language: str) -> None:
    """用目标机校验同一份冻结图和素材，允许不同的目录，只要执行输入一致。"""
    version = db.get(WorkflowVersion, task.version_id)
    if version is None:
        raise HTTPException(409, msg("workflow.notFound"))
    values = {
        key: AssetReference.model_validate(value) if isinstance(value, dict) else value
        for key, value in task.input_values.items()
    }
    graph, _, _, _ = compile_inputs(db, version, machine, values, None, language=language)
    if graph != task.input_graph:
        raise HTTPException(409, msg("input.theWorkMachineSInputConfiguration"))


def _online_machine(
    db: Session, owner_id: str, machine_id: str | None, team_id: str | None
) -> Machine:
    machine = db.scalar(
        select(Machine).where(
            Machine.id == machine_id,
            machine_scope(owner_id, team_id),
            Machine.visible(),
            Machine.revoked_at.is_(None),
        )
    )
    if machine is None:
        raise HTTPException(409, msg("task.selectAnAvailableWorkMachine"))
    if worker_type(machine.worker_kind).connection == "machine" and not machine_is_online(
        machine.last_seen, machine.revoked_at, now_ms()
    ):
        raise HTTPException(409, msg("task.theWorkMachineIsOfflineSelect"))
    return machine


def change_task_machine(db: Session, task: Task, machine_id: str, language: str) -> None:
    """在账号锁内换机，与领取串行。记录新的排队位置以便加入目标队列末尾。"""
    write_lock(db, Task, task.id)
    db.refresh(task)
    if (
        worker_type(task.worker_kind).service
        or task.status != Status.QUEUED
        or task.claim_id is not None
        or task.deleted_at is not None
    ):
        raise HTTPException(409, msg("task.onlyQueuedTasksCanChangeMachines"))
    if task.machine_id == machine_id:
        return
    machine = _online_machine(db, task.owner_id, machine_id, task.team_id)
    now = now_ms()
    validate_frozen_machine(db, task, machine, language)
    last = db.scalar(
        select(func.max(Task.queued_at)).where(
            Task.machine_id == machine.id,
            Task.status == Status.QUEUED,
            Task.visible(),
        )
    )
    task.machine_id = machine.id
    task.queued_at = max(now, (last or 0) + 1)
    task.updated_at = now


def _submission_key(key: str, team_id: str | None) -> str:
    # 个人记录保留原键。团队键加入空间标识，在同一账号的唯一约束下仍可分别重试。
    return digest(f"{team_id}:{key}") if team_id is not None else key


def _submitted_before(
    db: Session, user_id: str, team_id: str | None, key: str, request_hash: str
) -> Task | None:
    """返回同一账号同一幂等键已受理的任务。参数不同或记录已删除返回 HTTP 409。"""
    prior = db.scalar(
        select(Task).where(
            Task.owner_id == user_id, Task.team_id == team_id, Task.idempotency_key == key
        )
    )
    if prior is None:
        return None
    if prior.request_hash != request_hash:
        raise HTTPException(409, msg("task.theRepeatedRequestHasDifferentParameters"))
    if prior.deleted_at is not None:
        raise HTTPException(409, msg("task.theTaskRecordWasDeleted"))
    return prior


def retry_executions(
    db: Session,
    source: Task,
    body: TaskRetryRequest | ServiceRetryRequest,
    language: str,
    *,
    team: TeamAccess | None = None,
) -> tuple[Task, bool]:
    """从原批次冻结的执行快照建立一条新任务。补传和补跑在同一任务锁下互斥。"""
    indices = sorted(set(body.execution_indices))
    definition = worker_type(source.worker_kind)
    if definition.service != isinstance(body, ServiceRetryRequest):
        raise HTTPException(422, msg("task.noExecutionsToRetry"))
    machine_id = body.machine_id if isinstance(body, TaskRetryRequest) else source.machine_id
    actor_id = team.actor_id if team else source.owner_id
    key = _submission_key(body.idempotency_key, source.team_id)
    request_hash = digest(json.dumps(["retry", source.id, machine_id, indices]))
    prior = _submitted_before(db, actor_id, source.team_id, key, request_hash)
    if prior:
        return prior, False
    write_lock(db, Task, source.id)
    db.refresh(source)
    if (
        source.status not in (Status.FAILED, Status.CANCELLED)
        or source.claim_id is None
        or source.deleted_at is not None
    ):
        raise HTTPException(409, msg("task.noExecutionsToRetry"))
    selected = db.scalars(
        select(Execution)
        .where(Execution.task_id == source.id, Execution.index.in_(indices))
        .order_by(Execution.index)
    ).all()
    if len(selected) != len(indices) or any(
        execution.status not in (Status.FAILED, Status.CANCELLED)
        or execution.retry_task_id is not None
        or execution.submission_pending
        or (execution.prompt_id is not None and execution.recovery_status != "rerunnable")
        for execution in selected
    ):
        raise HTTPException(409, msg("task.noExecutionsToRetry"))
    workflow = readable_workflow(db, source.workflow_id, actor_id, team_id=source.team_id)
    readable_version(db, workflow, source.version_id, actor_id, team_id=source.team_id)
    if definition.connection == "account":
        original = matched(
            db.get(Machine, machine_id) if machine_id else None,
            source.worker_kind,
            (source.worker_data or {}).get("scope"),
            source.owner_id,
            team_id=source.team_id,
        )
        if original.connection_revision != source.connection_revision:
            raise HTTPException(409, msg("connection.reselectWorker"))
    if not definition.service:
        validate_frozen_machine(
            db, source, _online_machine(db, actor_id, machine_id, source.team_id), language
        )
    stamp = now_ms()
    task = Task(
        owner_id=actor_id,
        team_id=source.team_id,
        project_id=active_project_id(db, source.project_id),
        workflow_id=source.workflow_id,
        version_id=source.version_id,
        workflow_name=source.workflow_name,
        machine_id=machine_id,
        worker_kind=source.worker_kind,
        worker_data=source.worker_data,
        connection_revision=source.connection_revision,
        execution_count=len(selected),
        input_graph=source.input_graph,
        input_values=source.input_values,
        input_schema=source.input_schema,
        idempotency_key=key,
        request_hash=request_hash,
        created_at=stamp,
        queued_at=stamp,
    )
    db.add(task)
    db.flush()
    if team:
        team.record(db, "task.retried", task.id)
    for index, execution in enumerate(selected):
        execution.retry_task_id = task.id
        db.add(
            Execution(
                task_id=task.id,
                index=index,
                input_values=execution.input_values,
                created_at=stamp + index,
            )
        )
    bindings = db.scalars(select(TaskAsset).where(TaskAsset.task_id == source.id)).all()
    for binding in bindings:
        db.add(
            TaskAsset(
                task_id=task.id,
                asset_id=binding.asset_id,
                node_id=binding.node_id,
                input_name=binding.input_name,
            )
        )
    db.commit()
    return task, True


def generation_source(
    db: Session, body: GenerationInputs, owner_id: str, team_id: str | None
) -> tuple[Workflow, WorkflowVersion, Work | None]:
    workflow = readable_workflow(db, body.workflow_id, owner_id, team_id=team_id)
    version = readable_version(db, workflow, body.version_id, owner_id, team_id=team_id)
    if body.source_work_id and body.source_execution_id:
        raise HTTPException(422, msg("workflow.selectASingleSourceForThe"))
    if body.source_execution_id:
        _, source_task = owned_execution(db, body.source_execution_id, owner_id, team_id=team_id)
        if source_task.workflow_id != workflow.id or source_task.version_id != version.id:
            raise HTTPException(422, msg("task.theRerunSourceDoesNotMatch"))
    source = None
    if body.source_work_id:
        source = readable_work(db, body.source_work_id, owner_id, team_id=team_id)
        if source.workflow_id != workflow.id or source.version_id != version.id:
            raise HTTPException(422, msg("task.theRerunSourceDoesNotMatch"))
    return workflow, version, source


def submit_task(
    db: Session,
    user: User,
    body: TaskCreate,
    config: Settings,
    language: str,
    *,
    team: TeamAccess | None = None,
) -> tuple[Task, bool]:
    """在调用方锁定的账号下校验输入并写入排队任务，返回任务及是否新建。

    同一账号重复提交相同幂等键和参数时返回原任务。个人任务使用匹配的工作机，
    平台托管任务由对应服务领取。参数冲突返回 409，重跑来源不匹配或提交 UI 图返回 422。
    """
    # 无项目时沿用既有提交摘要，部署前后的同键重试仍能找到原任务。
    project_id = str(body.project_id) if body.project_id else None
    fields = body.model_dump(exclude={"idempotency_key", "project_id"})
    if project_id:
        fields["project_id"] = project_id
    request_hash = digest(json.dumps(fields, sort_keys=True, separators=(",", ":")))
    team_id = team.team.id if team else None
    key = _submission_key(body.idempotency_key, team_id)
    prior = _submitted_before(db, user.id, team_id, key, request_hash)
    if prior:
        return prior, False
    if project_id:
        active_project(db, project_id, user.id, team_id)
    workflow, version, source = generation_source(db, body, user.id, team_id)
    if version.format == "ui":
        raise HTTPException(422, msg("input.exportTheApiVersionOfThe"))
    definition = worker_type(version.worker_kind)
    machine = None
    if definition.connection == "platform":
        if body.machine_id is not None:
            raise HTTPException(422, msg("input.thisParameterDoesNotBelongTo"))
    else:
        pref = machine_preference(db, user.id, team_id)
        machine_id = body.machine_id
        if not machine_id and definition.connection == "account":
            candidates = db.scalars(
                select(Machine.id)
                .where(
                    machine_scope(user.id, team_id),
                    Machine.worker_kind == definition.kind,
                    Machine.connection_scope == version.connection_scope,
                    Machine.revoked_at.is_(None),
                    Machine.visible(),
                )
                .limit(2)
            ).all()
            if len(candidates) != 1:
                raise HTTPException(409, msg("connection.selectForRun"))
            machine_id = candidates[0]
        machine_id = machine_id or (pref.default_machine_id if pref else None)
        machine = matched(
            _online_machine(db, user.id, machine_id, team_id),
            version.worker_kind,
            version.connection_scope,
            user.id,
            team_id=team_id,
        )
    values = (
        reuse_work_inputs(db, source, user.id, body.input_values, config, team_id=team_id)
        if source is not None
        else body.input_values
    )
    input_graph, input_values, input_schema, assets = compile_inputs(
        db,
        version,
        machine,
        values,
        body.input_schema_hash,
        owner_id=user.id,
        team_id=team_id,
        language=language,
    )
    ensure_quota_for_reuse(
        db,
        user.id,
        [asset.asset_id for asset in assets],
        config.asset_quota_for(team_id),
        team_id=team_id,
    )
    stamp = now_ms()
    task = Task(
        owner_id=user.id,
        team_id=team_id,
        project_id=project_id,
        workflow_id=workflow.id,
        version_id=version.id,
        workflow_name=workflow.name,
        execution_count=body.execution_count,
        idempotency_key=key,
        request_hash=request_hash,
        machine_id=machine.id if machine else None,
        worker_kind=definition.kind,
        connection_revision=machine.connection_revision if machine else None,
        worker_data={
            "scope": version.connection_scope,
            "reference": (version.worker_data or {}).get("reference"),
            "graph_hash": version.graph_hash,
            "connection_name": machine.name,
        }
        if machine and definition.connection == "account"
        else None,
        input_graph=input_graph,
        input_values=input_values,
        input_schema=input_schema,
        source_execution_id=body.source_execution_id,
        source_work_id=body.source_work_id,
        created_at=stamp,
        queued_at=stamp,
    )
    db.add(task)
    try:
        # 任务、各次执行的快照和素材绑定在同一事务内写入。
        db.flush()
        if team:
            team.record(db, "task.submitted", task.id)
        create_executions(db, task)
        for asset in assets:
            asset.task_id = task.id
            db.add(asset)
        db.commit()
    except IntegrityError:
        # 并发的同键提交由唯一约束拦下，按已受理的那一条应答。
        db.rollback()
        prior = _submitted_before(db, user.id, team_id, key, request_hash)
        if prior is None:
            # 没有同键任务时冲突来自引用：所选素材或来源在校验之后被删除了。
            raise HTTPException(409, msg("task.theSelectedAssetOrSourceIs")) from None
        return prior, False
    return task, True


def assign_project(
    db: Session, task: Task, project_id: str | None, team: TeamAccess | None
) -> None:
    if project_id:
        active_project(db, project_id, task.owner_id, task.team_id)
    if task.project_id != project_id:
        task.project_id = project_id
        if team:
            team.record(db, "task.projectChanged", task.id)
        db.commit()


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
        raise HTTPException(409, msg("task.thisTaskHasAlreadyEnded"))
    stamp = now_ms()
    lease_expires_at = task.lease_expires_at
    record_official_wait(db, task, stamp, "ended")
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
        raise HTTPException(409, msg("task.onlyTasksCanceledBeforeStartingCan"))
    # 取消之后工作机可能已被撤销，素材也可能过了保留期被清理，这样的任务回到队列也执行不了。
    machine = (
        db.scalar(
            select(Machine).where(
                Machine.id == task.machine_id, machine_scope(task.owner_id, task.team_id)
            )
        )
        if task.machine_id
        else None
    )
    if task.connection_revision and (
        not machine or machine.connection_revision != task.connection_revision
    ):
        raise HTTPException(409, msg("connection.reselectWorker"))
    if worker_type(task.worker_kind).connection != "platform" and (
        machine is None or machine.revoked_at is not None
    ):
        raise HTTPException(409, msg("task.theTaskSWorkMachineWas"))
    wanted = {
        value["assetId"]
        for value in task.input_values.values()
        if isinstance(value, dict) and "assetId" in value
    }
    bound = set(db.scalars(select(TaskAsset.asset_id).where(TaskAsset.task_id == task.id)))
    if wanted - bound:
        raise HTTPException(409, msg("task.theTaskSAssetsWereRemoved"))
    stamp = now_ms()
    task.status = Status.QUEUED
    task.cloud_cancel = None
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
        raise HTTPException(409, msg("task.onlyFinishedTasksCanBeDeleted"))
    task.mark_deleted()


def restore_task(db: Session, task: Task, config: Settings) -> None:
    """撤销删除任务记录，由调用方提交。

    删除时释放的素材随任务重新计入配额，放回后超出空间上限返回 413。
    """
    ensure_quota_for_restore(db, task, config)
    db.refresh(task)
    task.restore()
