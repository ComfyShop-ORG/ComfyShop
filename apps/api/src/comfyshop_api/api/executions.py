from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select, tuple_

from comfyshop_api.models import Status, Artifact, Execution, Task
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ExecutionCoverUpdate,
    ExecutionPage,
    ExecutionRead,
    ReplayRead,
)
from comfyshop_api.security import Config, CurrentUser, DB, Writer
from comfyshop_api.services.assets import ensure_quota_for_restore
from comfyshop_api.services.artifacts import (
    delete_result_artifacts,
    lock_execution_media,
    restore_result_artifacts,
)
from comfyshop_media.renditions import cover_frame
from comfyshop_api.services.media_records import media_source
from comfyshop_api.services.executions import execution_reads, owned_execution
from comfyshop_api.services.workflows import replay_workflow_read

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=ExecutionPage)
def list_executions(
    db: DB,
    user: CurrentUser,
    workflow_id: str | None = None,
    task_id: str | None = None,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
):
    members = select(Artifact.id).where(Artifact.execution_id == Execution.id).correlate(Execution)
    query = (
        select(Execution, Task)
        .join(Task, Task.id == Execution.task_id)
        .where(
            Task.owner_id == user.id,
            Execution.status == Status.SUCCEEDED,
            # 只收起因删除而空的结果组。历史执行的状态与输入仍可读取。
            ~members.where(Artifact.deleted_at.is_not(None)).exists()
            | members.where(Artifact.visible()).exists(),
        )
    )
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if task_id:
        query = query.where(Task.id == task_id)
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(Execution.created_at, Execution.id) < tuple(position))
    records = db.execute(
        query.order_by(Execution.created_at.desc(), Execution.id.desc()).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(records, limit, lambda row: (row[0].created_at, row[0].id))
    return ExecutionPage(items=execution_reads(db, items), next_cursor=next_cursor)


@router.get("/{execution_id}", response_model=ExecutionRead)
def get_execution(execution_id: str, db: DB, user: CurrentUser):
    return execution_reads(db, [owned_execution(db, execution_id, user.id)])[0]


@router.delete("/{execution_id}/artifacts", status_code=204)
def delete_execution_artifacts(execution_id: str, db: DB, user: Writer) -> Response:
    execution, _ = owned_execution(db, execution_id, user.id)
    delete_result_artifacts(db, execution)
    db.commit()
    return Response(status_code=204)


# 撤销最近一次整组删除。
@router.post("/{execution_id}/artifacts/restore", response_model=ExecutionRead)
def restore_execution_artifacts(
    execution_id: str, db: DB, user: Writer, config: Config
) -> ExecutionRead:
    execution, task = owned_execution(db, execution_id, user.id)
    # 已删除任务的成品恢复后，任务的素材重新计入配额。
    ensure_quota_for_restore(db, user.id, task.id, config.asset_quota_bytes)
    restore_result_artifacts(db, execution)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


# 指定结果分组的封面。所选成品须属于这次成功执行且未被删除。封面是视频时可用
# `frame_ms` 指定取哪一刻的画面，不传则用首帧；时间超出视频长度返回 422。
@router.put("/{execution_id}/cover", response_model=ExecutionRead)
def set_execution_cover(
    execution_id: str, body: ExecutionCoverUpdate, db: DB, user: Writer, config: Config
):
    execution, task = owned_execution(db, execution_id, user.id)
    chosen = select(Artifact).where(
        Artifact.id == body.artifact_id,
        Artifact.execution_id == execution.id,
        Artifact.visible(),
    )
    artifact = db.scalar(chosen)
    if execution.status != Status.SUCCEEDED or not artifact:
        raise HTTPException(404, "成品不存在")
    # 截取画面可能要几秒，在取得写锁之前完成。
    frame_ms = cover_frame(media_source(artifact.media), config, body.frame_ms)
    lock_execution_media(db, execution.id)
    if not db.scalar(chosen.execution_options(populate_existing=True)):
        raise HTTPException(404, "成品不存在")
    execution.cover_artifact_id = artifact.id
    execution.cover_frame_ms = frame_ms
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


@router.get("/{execution_id}/replay", response_model=ReplayRead)
def replay_execution(execution_id: str, db: DB, user: CurrentUser):
    execution, task = owned_execution(db, execution_id, user.id)
    return ReplayRead(
        workflow=replay_workflow_read(db, task.workflow_id, task.version_id, user.id),
        source_execution_id=execution.id,
    )
