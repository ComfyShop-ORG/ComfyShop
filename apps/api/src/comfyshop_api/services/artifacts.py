"""成品软删除，以及失败或取消执行留下的部分文件回收。"""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Status,
    Artifact,
    Execution,
    Machine,
    Task,
    Work,
    WorkArtifact,
    now_ms,
)

from comfyshop_api.services.executions import execution_at
from comfyshop_api.services.machines import fence
from comfyshop_api.services.originals import attach_original
from comfyshop_media.uploads import ReceivedMedia

CLEANUP_BATCH_SIZE = 100


@dataclass(frozen=True)
class ArtifactUpload:
    """工作机为一份成品声明的回传编号、内容摘要和输出来源。"""

    client_id: str
    sha256: str
    execution_index: int
    output_node_id: str
    output_slot: str
    output_index: int


def _uploaded_before(db: Session, task_id: str, execution_id: str, upload: ArtifactUpload):
    """返回同一回传编号已保存的成品。内容或输出来源不同返回 HTTP 409。"""
    prior = db.scalar(
        select(Artifact).where(Artifact.task_id == task_id, Artifact.client_id == upload.client_id)
    )
    if prior is None:
        return None
    if (
        prior.sha256 != upload.sha256
        or prior.execution_id != execution_id
        or prior.output_node_id != upload.output_node_id
        or prior.output_slot != upload.output_slot
        or prior.output_index != upload.output_index
    ):
        raise HTTPException(409, "重复上传的文件不一致")
    return prior


def begin_artifact_upload(db: Session, task: Task, upload: ArtifactUpload) -> Artifact | str:
    """在接收文件前核对回传目标。重试时返回已保存的成品，否则返回输出节点标题。

    任务或执行已结束返回 HTTP 409，输出节点不在冻结图内返回 422。
    """
    execution = execution_at(db, task, upload.execution_index)
    prior = _uploaded_before(db, task.id, execution.id, upload)
    if prior:
        return prior
    if task.status != Status.RUNNING:
        raise HTTPException(409, "任务已结束")
    if execution.status not in Status.ACTIVE:
        raise HTTPException(409, "执行已结束")
    node = task.input_graph.get(upload.output_node_id)
    if not node:
        raise HTTPException(422, "输出节点不属于工作流")
    return str((node.get("_meta") or {}).get("title") or node["class_type"])[:160]


def record_artifact(
    db: Session,
    task_id: str,
    machine: Machine,
    lease: str | None,
    upload: ArtifactUpload,
    filename: str,
    node_title: str,
    media: ReceivedMedia,
    limit: int,
    stored: bool,
) -> tuple[Artifact, Task]:
    """重新核对租约并保存成品记录。

    `limit` 是一次执行可回传的成品数。
    租约或执行已失效返回 HTTP 409，数量超限返回 413。
    """
    task = fence(db, task_id, machine, lease)
    # 条件更新同时取得写锁并确认租约仍有效，随后的数量检查和插入不会与并发回传交错。
    locked = db.execute(
        update(Task)
        .where(Task.id == task.id, Task.status == Status.RUNNING, Task.lease_expires_at > now_ms())
        .values(updated_at=now_ms())
    )
    if not cast(CursorResult, locked).rowcount:
        raise HTTPException(409, "任务租约已失效")
    execution = execution_at(db, task, upload.execution_index)
    db.refresh(execution)
    prior = _uploaded_before(db, task_id, execution.id, upload)
    if prior is not None:
        return prior, task
    if execution.status not in Status.ACTIVE:
        raise HTTPException(409, "执行已结束")
    count = db.scalars(
        select(func.count()).select_from(Artifact).where(Artifact.execution_id == execution.id)
    ).one()
    if count >= limit:
        raise HTTPException(413, "成品数量超出限制")
    artifact = Artifact(
        task_id=task_id,
        owner_id=task.owner_id,
        client_id=upload.client_id,
        execution_id=execution.id,
        output_node_id=upload.output_node_id,
        output_node_title=node_title,
        output_slot=upload.output_slot,
        output_index=upload.output_index,
        filename=Path(filename.replace("\\", "/")).name,
        media=attach_original(db, media, stored),
    )
    db.add(artifact)
    try:
        db.commit()
    except IntegrityError:
        # 并发的同编号回传由唯一约束拦下，按已保存的那一份应答。
        db.rollback()
        prior = _uploaded_before(db, task_id, execution.id, upload)
        if prior is None:
            raise HTTPException(409, "重复上传的文件不一致") from None
        return prior, task
    return artifact, task


def lock_execution_media(db: Session, execution_id: str) -> None:
    """用数据库写锁串行化同一组的删除、发布和封面操作，锁随事务结束释放。"""
    write_lock(db, Execution, execution_id)


def delete_result_artifacts(
    db: Session, execution: Execution, artifact_id: str | None = None
) -> None:
    """标记一份或整组成功成品为已删除，由调用方提交。

    仍被作品使用时返回 409。原文件和引用继续保留，读取时过滤已删除的成品。
    """
    if execution.status != Status.SUCCEEDED:
        raise HTTPException(409, "只能删除已完成执行的成品")
    lock_execution_media(db, execution.id)
    available = select(Artifact.id).where(Artifact.execution_id == execution.id, Artifact.visible())
    targets = available.where(Artifact.id == artifact_id) if artifact_id else available
    ids = list(db.scalars(targets))
    if not ids:
        return
    used_by_work = (
        select(Work.id)
        .where(
            Work.visible(),
            or_(
                Work.cover_artifact_id.in_(ids),
                Work.id.in_(select(WorkArtifact.work_id).where(WorkArtifact.artifact_id.in_(ids))),
            ),
        )
        .exists()
    )
    if db.scalar(select(used_by_work)):
        raise HTTPException(409, "成品已用于作品，请先删除对应作品")

    db.execute(update(Artifact).where(Artifact.id.in_(ids)).values(deleted_at=now_ms()))


def restore_result_artifacts(db: Session, execution: Execution) -> None:
    """撤销最近一次对这组成品的删除，由调用方提交。

    同一次删除的成品带有相同的删除时间。更早单独删除的成品保持删除状态。
    """
    lock_execution_media(db, execution.id)
    latest = db.scalar(
        select(func.max(Artifact.deleted_at)).where(Artifact.execution_id == execution.id)
    )
    if latest is not None:
        db.execute(
            update(Artifact)
            .where(Artifact.execution_id == execution.id, Artifact.deleted_at == latest)
            .values(deleted_at=None)
        )


def is_cover_frame(db: Session, artifact_id: str, frame_ms: int) -> bool:
    """视频这一刻的画面是否被某个结果组或作品选作封面。

    带时间点的缩略图只为选中的画面提供：否则读得到视频的人可以逐毫秒请求，让缓存无限增长。
    """
    for model in (Execution, Work):
        chosen = select(model.id).where(
            model.cover_artifact_id == artifact_id, model.cover_frame_ms == frame_ms
        )
        if db.scalar(chosen.limit(1)):
            return True
    return False


def expire_incomplete_artifacts(db: Session, config: Settings) -> None:
    cutoff = now_ms() - config.failed_artifact_ttl_seconds * 1000
    candidates = list(
        db.scalars(
            select(Artifact.id)
            .join(Execution, Execution.id == Artifact.execution_id)
            .where(
                Execution.status.in_((Status.FAILED, Status.CANCELLED)),
                Execution.updated_at <= cutoff,
                Artifact.visible(),
            )
            .order_by(Execution.updated_at, Execution.id, Artifact.id)
            .limit(CLEANUP_BATCH_SIZE)
        )
    )
    db.rollback()
    if candidates:
        db.execute(delete(Artifact).where(Artifact.id.in_(candidates)))
        db.commit()
