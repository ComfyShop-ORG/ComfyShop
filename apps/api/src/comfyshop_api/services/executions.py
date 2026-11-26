"""保存单次执行的冻结输入，校验输出清单，并组装结果页所需的执行资料。"""

from collections import Counter
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Row, func, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import (
    Artifact,
    Execution,
    Status,
    Task,
    now_ms,
)
from comfyshop_api.schemas import ExecutionRead, JobSeed
from comfyshop_api.security import workspace_records
from comfyshop_api.services.inputs import plan_execution_seeds, seed_fields
from comfyshop_api.services.media_records import (
    artifact_media,
    cover_image_read,
    media_kind,
    preferred_cover,
)
from comfyshop_api.services.parameter_features import qwen_prompt_preview
from comfyshop_api.services.worker_types import worker_type
from comfyshop_media.model_exports import MESH_CONTENT_TYPES


def create_executions(db: Session, task: Task) -> None:
    """按 `task.execution_count` 建立执行行，并冻结每次的种子。由提交任务的事务统一提交。"""
    fields = (
        [] if worker_type(task.worker_kind).form == "fields" else seed_fields(task.input_schema)
    )
    planned = plan_execution_seeds(fields, task.input_values, task.execution_count)
    for index, seeds in enumerate(planned):
        db.add(
            Execution(
                task_id=task.id,
                index=index,
                input_values={**task.input_values, **seeds},
                created_at=task.created_at + index,
            )
        )


def execution_seed_bindings(db: Session, task: Task) -> list[list[JobSeed]]:
    """按执行序号返回工作机所需的种子绑定，用十进制字符串保留精度。

    种子在提交任务时已冻结到每次执行的快照。快照缺少执行或种子时返回 HTTP 409。
    """
    fields = seed_fields(task.input_schema)
    if not fields:
        return [[] for _ in range(task.execution_count)]
    rows = db.scalars(
        select(Execution).where(Execution.task_id == task.id).order_by(Execution.index)
    ).yield_per(1)
    bindings = []
    for index, execution in enumerate(rows):
        if execution.index != index or index >= task.execution_count:
            raise HTTPException(409, msg("execution.incompleteTaskSnapshot"))
        if any(field.id not in execution.input_values for field in fields):
            raise HTTPException(409, msg("execution.theTaskSnapshotHasNoSeed"))
        bindings.append(
            [
                JobSeed(
                    node_id=field.node_id,
                    input_name=field.input_name,
                    value=str(execution.input_values[field.id]),
                )
                for field in fields
            ]
        )
    if len(bindings) != task.execution_count:
        raise HTTPException(409, msg("execution.incompleteTaskSnapshot"))
    return bindings


def execution_at(db: Session, task: Task, index: int) -> Execution:
    execution = db.scalar(
        select(Execution).where(Execution.task_id == task.id, Execution.index == index)
    )
    if not execution:
        raise HTTPException(422, msg("execution.invalidRunNumber"))
    return execution


def task_executions_complete() -> ColumnElement[bool]:
    executions = select(Execution.id).where(Execution.task_id == Task.id).correlate(Task)
    count = executions.with_only_columns(func.count(Execution.id)).scalar_subquery()
    unfinished = executions.where(Execution.status != Status.SUCCEEDED).exists()
    return (count == Task.execution_count) & ~unfinished


def owned_execution(
    db: Session, execution_id: str, user_id: str, *, team_id: str | None = None
) -> tuple[Execution, Task]:
    record = db.execute(
        select(Execution, Task)
        .join(Task, Task.id == Execution.task_id)
        .where(
            Execution.id == execution_id,
            workspace_records(Task.owner_id, Task.team_id, user_id, team_id),
        )
    ).first()
    if not record:
        raise HTTPException(404, msg("workflow.runNotFound"))
    return record[0], record[1]


def task_has_results(task_id: str | InstrumentedAttribute[str]) -> ColumnElement[bool]:
    return (
        select(Artifact.id)
        .join(Execution, Artifact.execution_id == Execution.id)
        .where(
            Artifact.task_id == task_id, Artifact.visible(), Execution.status == Status.SUCCEEDED
        )
        .exists()
    )


def execution_reads(
    db: Session, records: Sequence[tuple[Execution, Task] | Row[tuple[Execution, Task]]]
) -> list[ExecutionRead]:
    ids = [execution.id for execution, _ in records]
    members: dict[str, list[Artifact]] = {id_: [] for id_ in ids}
    if ids:
        for artifact in db.scalars(
            select(Artifact)
            .where(Artifact.execution_id.in_(ids), Artifact.visible())
            .order_by(Artifact.output_index, Artifact.id)
        ):
            members[artifact.execution_id].append(artifact)
    result = []
    for execution, task in records:
        artifacts = members[execution.id]
        counts = Counter(media_kind(artifact.content_type) for artifact in artifacts)
        cover = next((a for a in artifacts if a.id == execution.cover_artifact_id), None)
        # 选定的画面只属于用户指定的那份封面；它被删除后改用的封面从首帧开始。
        frame_ms = execution.cover_frame_ms if cover else None
        if cover is None and artifacts:
            cover = preferred_cover(artifacts)
        result.append(
            ExecutionRead(
                id=execution.id,
                task_id=task.id,
                task_owner_id=task.owner_id,
                project_id=task.project_id,
                workflow_id=task.workflow_id,
                workflow_name=task.workflow_name,
                version_id=task.version_id,
                index=execution.index,
                status=execution.status,
                prompt_id=execution.prompt_id,
                input_values=execution.input_values,
                effective_prompt=execution.effective_prompt,
                prompt_expanded=preview[1]
                if execution.effective_prompt and (preview := qwen_prompt_preview(task.input_graph))
                else None,
                cover_artifact_id=cover.id if cover else None,
                cover_frame_ms=frame_ms,
                cover_image=cover_image_read("executions", execution.id, execution.cover_image)
                if artifacts
                else None,
                media=artifact_media(cover, frame_ms) if cover else None,
                image_count=counts["image"],
                video_count=counts["video"],
                audio_count=counts["audio"],
                model_count=sum(a.content_type in MESH_CONTENT_TYPES for a in artifacts),
                text_count=counts["text"],
                artifact_count=len(artifacts),
                created=execution.created_at,
            )
        )
    return result


def finish_execution(
    db: Session,
    execution: Execution,
    client_ids: list[str],
    effective_prompt: str | None = None,
    *,
    recovering: bool = False,
) -> None:
    """核对已上传文件及顺序，写入清单并标记成功。由调用方提交事务。

    已成功的执行可重放同一份 `client_ids` 清单。清单重复编号返回 422，
    顺序不符、缺少成品或执行已结束返回 409。
    """
    if len(set(client_ids)) != len(client_ids):
        raise HTTPException(422, msg("execution.anOutputAppearsMoreThanOnce"))
    if execution.status == Status.SUCCEEDED:
        if execution.manifest != client_ids:
            raise HTTPException(409, msg("execution.theRunOutputsDoNotMatch"))
        if effective_prompt is not None and execution.effective_prompt != effective_prompt:
            raise HTTPException(409, msg("execution.theRunPromptDoesNotMatch"))
        return
    if execution.status not in Status.ACTIVE and not recovering:
        raise HTTPException(409, msg("media.theRunHasEnded"))
    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(Artifact.execution_id == execution.id)
            .order_by(Artifact.output_index, Artifact.id)
        )
    )
    if not artifacts or [a.client_id for a in artifacts] != client_ids:
        raise HTTPException(409, msg("execution.theRunOutputsHaveNotFully"))
    execution.manifest = client_ids
    execution.effective_prompt = effective_prompt
    execution.status = Status.SUCCEEDED
    execution.recovery_status = None
    execution.updated_at = now_ms()


def fail_official_execution(
    task: Task, execution: Execution, error: str, *, retryable: bool
) -> None:
    if execution.status == Status.FAILED:
        return
    if task.status != Status.RUNNING or execution.status not in Status.ACTIVE:
        raise HTTPException(409, msg("media.theRunHasEnded"))
    execution.status = Status.FAILED
    execution.updated_at = now_ms()
    if retryable:
        execution.submission_pending = False
        execution.recovery_status = "rerunnable"
    if task.error is None or not retryable:
        task.error = error


def fail_unfinished_executions(db: Session, task_id: str, status: Status) -> None:
    db.execute(
        update(Execution)
        .where(Execution.task_id == task_id, Execution.status.in_(Status.ACTIVE))
        .values(status=status, updated_at=now_ms())
    )
