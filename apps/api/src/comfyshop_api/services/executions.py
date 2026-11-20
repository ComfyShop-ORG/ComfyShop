"""保存单次执行的冻结输入，校验输出清单，并组装结果页所需的执行资料。"""

from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import Row, ColumnElement, func, select, update
from sqlalchemy.orm import Session

from comfyshop_api.models import (
    Status,
    StatusValue,
    Artifact,
    Execution,
    Task,
    now_ms,
)
from comfyshop_api.schemas import ExecutionRead, JobSeed
from comfyshop_api.services.inputs import plan_execution_seeds, seed_fields
from comfyshop_api.services.media_records import artifact_media, cover_image_read, preferred_cover


def create_executions(db: Session, task: Task) -> None:
    """按 `task.execution_count` 建立执行行，并冻结每次的种子。由提交任务的事务统一提交。"""
    fields = seed_fields(task.input_schema)
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
            raise HTTPException(409, "任务执行快照不完整")
        if any(field.id not in execution.input_values for field in fields):
            raise HTTPException(409, "任务执行快照缺少种子")
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
        raise HTTPException(409, "任务执行快照不完整")
    return bindings


def execution_at(db: Session, task: Task, index: int) -> Execution:
    execution = db.scalar(
        select(Execution).where(Execution.task_id == task.id, Execution.index == index)
    )
    if not execution:
        raise HTTPException(422, "执行序号无效")
    return execution


def task_executions_complete() -> ColumnElement[bool]:
    executions = select(Execution.id).where(Execution.task_id == Task.id).correlate(Task)
    count = executions.with_only_columns(func.count(Execution.id)).scalar_subquery()
    unfinished = executions.where(Execution.status != Status.SUCCEEDED).exists()
    return (count == Task.execution_count) & ~unfinished


def owned_execution(db: Session, execution_id: str, user_id: str) -> tuple[Execution, Task]:
    record = db.execute(
        select(Execution, Task)
        .join(Task, Task.id == Execution.task_id)
        .where(Execution.id == execution_id, Task.owner_id == user_id)
    ).first()
    if not record:
        raise HTTPException(404, "执行不存在")
    return record[0], record[1]


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
        cover = next((a for a in artifacts if a.id == execution.cover_artifact_id), None)
        # 选定的画面只属于用户指定的那份封面；它被删除后改用的封面从首帧开始。
        frame_ms = execution.cover_frame_ms if cover else None
        if cover is None and artifacts:
            cover = preferred_cover(artifacts)
        result.append(
            ExecutionRead(
                id=execution.id,
                task_id=task.id,
                workflow_id=task.workflow_id,
                workflow_name=task.workflow_name,
                version_id=task.version_id,
                index=execution.index,
                status=execution.status,
                prompt_id=execution.prompt_id,
                input_values=execution.input_values,
                cover_artifact_id=cover.id if cover else None,
                cover_frame_ms=frame_ms,
                cover_image=cover_image_read("executions", execution.id, execution.cover_image)
                if artifacts
                else None,
                media=artifact_media(cover, frame_ms) if cover else None,
                image_count=sum(a.media.content_type.startswith("image/") for a in artifacts),
                video_count=sum(a.media.content_type.startswith("video/") for a in artifacts),
                audio_count=sum(a.media.content_type.startswith("audio/") for a in artifacts),
                model_count=sum(a.media.content_type == "model/gltf-binary" for a in artifacts),
                artifact_count=len(artifacts),
                created=execution.created_at,
            )
        )
    return result


def finish_execution(db: Session, execution: Execution, client_ids: list[str]) -> None:
    """核对已上传文件及顺序，写入清单并标记成功。由调用方提交事务。

    已成功的执行可重放同一份 `client_ids` 清单。清单重复编号返回 422，
    顺序不符、缺少成品或执行已结束返回 409。
    """
    if len(set(client_ids)) != len(client_ids):
        raise HTTPException(422, "成品清单不能重复")
    if execution.status == Status.SUCCEEDED:
        if execution.manifest != client_ids:
            raise HTTPException(409, "执行成品清单不一致")
        return
    if execution.status not in Status.ACTIVE:
        raise HTTPException(409, "执行已结束")
    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(Artifact.execution_id == execution.id)
            .order_by(Artifact.output_index, Artifact.id)
        )
    )
    if not artifacts or [a.client_id for a in artifacts] != client_ids:
        raise HTTPException(409, "执行成品尚未完整回传")
    execution.manifest = client_ids
    execution.status = Status.SUCCEEDED
    execution.updated_at = now_ms()


def fail_unfinished_executions(db: Session, task_id: str, status: StatusValue) -> None:
    db.execute(
        update(Execution)
        .where(Execution.task_id == task_id, Execution.status.in_(Status.ACTIVE))
        .values(status=status, updated_at=now_ms())
    )
