"""读取和发布作品。作品是成品对外公开的唯一途径。"""

import json

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from comfyshop_api.models import (
    Status,
    Artifact,
    Execution,
    Task,
    User,
    Work,
    WorkArtifact,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.schemas import WorkCreate, WorkRead
from comfyshop_api.security import digest
from comfyshop_api.services.artifacts import lock_execution_media
from comfyshop_api.services.executions import owned_execution
from comfyshop_api.services.media_records import artifact_media


def readable_work(db: Session, work_id: str, user_id: str | None) -> Work:
    work = db.get(Work, work_id)
    workflow = db.get(Workflow, work.workflow_id) if work else None
    if (
        not work
        or work.deleted_at is not None
        or not workflow
        or (
            work.owner_id != user_id
            and (not work.published or not workflow.published or workflow.deleted_at)
        )
    ):
        raise HTTPException(404, "作品不存在")
    return work


def public_work_condition():
    return (
        Work.visible()
        & Work.published.is_(True)
        & Workflow.published.is_(True)
        & Workflow.visible()
    )


def restore_deleted_work(db: Session, work: Work) -> None:
    """在成品写锁内恢复作品。引用的成品已删除时返回 409，由调用方提交。"""
    lock_execution_media(db, work.execution_id)
    db.refresh(work)
    if work.deleted_at is None:
        return
    missing = (
        select(Artifact.id)
        .join(WorkArtifact, WorkArtifact.artifact_id == Artifact.id)
        .where(WorkArtifact.work_id == work.id, ~Artifact.visible())
        .exists()
    )
    if db.scalar(select(missing)):
        raise HTTPException(409, "作品中的成品已删除，请先恢复成品")
    work.restore()


def artifact_public(db: Session, artifact_id: str) -> bool:
    """成品是否被某个公开作品选中。调用方还需检查所属执行已经成功。"""
    return bool(
        db.scalar(
            select(
                exists(
                    select(WorkArtifact.artifact_id)
                    .join(Work)
                    .join(Workflow)
                    .where(WorkArtifact.artifact_id == artifact_id, public_work_condition())
                )
            )
        )
    )


def work_reads(db: Session, works: list[Work]) -> list[WorkRead]:
    if not works:
        return []
    covers = {
        a.id: a
        for a in db.scalars(
            select(Artifact).where(Artifact.id.in_([w.cover_artifact_id for w in works]))
        )
    }
    owners = {
        u.id: u.username
        for u in db.scalars(select(User).where(User.id.in_([w.owner_id for w in works])))
    }
    tasks = {
        e.id: t
        for e, t in db.execute(
            select(Execution, Task)
            .join(Task, Task.id == Execution.task_id)
            .where(Execution.id.in_([w.execution_id for w in works]))
        )
    }
    counts: dict[str, int] = dict(
        db.execute(
            select(WorkArtifact.work_id, func.count())
            .where(WorkArtifact.work_id.in_([w.id for w in works]))
            .group_by(WorkArtifact.work_id)
        )
        .tuples()
        .all()
    )
    return [
        WorkRead(
            id=w.id,
            title=w.title,
            author=owners[w.owner_id],
            owner=w.owner_id,
            workflow_id=w.workflow_id,
            workflow_name=tasks[w.execution_id].workflow_name,
            version_id=w.version_id,
            execution_id=w.execution_id,
            cover_artifact_id=w.cover_artifact_id,
            cover_frame_ms=w.cover_frame_ms,
            media=artifact_media(covers[w.cover_artifact_id], w.cover_frame_ms),
            asset_count=counts[w.id],
            published=w.published,
            input_values=w.input_values,
            created=w.created_at,
            description=w.description or "",
        )
        for w in works
    ]


def _published_before(db: Session, work_id: str, user_id: str, request_hash: str) -> Work | None:
    """返回同一发布编号已保存的作品。归属或内容不同、作品已删除返回 HTTP 409。"""
    prior = db.get(Work, work_id)
    if prior is None:
        return None
    if prior.owner_id != user_id or prior.request_hash != request_hash:
        raise HTTPException(409, "重复发布的内容不一致")
    if prior.deleted_at is not None:
        raise HTTPException(409, "作品已删除")
    return prior


def publish_work(db: Session, user_id: str, body: WorkCreate) -> tuple[Work, bool]:
    """从本人一次成功执行的所选成品建立作品，返回作品及是否新建。

    相同发布编号和内容返回原作品。执行未成功、来源版本或工作流未发布返回 HTTP 409，
    成品不属于此次执行返回 404，封面不在所选成品内或成品重复返回 422。
    """
    request_hash = digest(json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")))
    prior = _published_before(db, body.id, user_id, request_hash)
    if prior:
        return prior, False
    execution, task = owned_execution(db, body.execution_id, user_id)
    workflow = db.get(Workflow, task.workflow_id)
    if workflow is None:
        raise HTTPException(404, "工作流不存在")
    if execution.status != Status.SUCCEEDED:
        raise HTTPException(409, "只能发布成功执行的成品")
    # 作品公开来源版本的成品和参数说明，访客还要能用同一版本重跑，草稿版本的结果不能发布。
    version = db.get(WorkflowVersion, task.version_id)
    if workflow.deleted_at is None and (version is None or not version.published):
        raise HTTPException(409, "这次结果来自未发布的工作流版本，只能发布已发布版本的结果")
    if not workflow.published or workflow.deleted_at:
        raise HTTPException(409, "请先发布工作流")
    if (
        len(set(body.artifact_ids)) != len(body.artifact_ids)
        or body.cover_artifact_id not in body.artifact_ids
    ):
        raise HTTPException(422, "作品封面必须属于所选成品，成品不能重复")
    lock_execution_media(db, execution.id)
    members = db.scalars(
        select(Artifact).where(
            Artifact.execution_id == execution.id,
            Artifact.id.in_(body.artifact_ids),
            Artifact.visible(),
        )
    ).all()
    if len(members) != len(body.artifact_ids):
        raise HTTPException(404, "所选成品不属于此次执行")
    values = {}
    if body.share_parameters:
        # 只公开节点定义内的标量输入，参考素材引用始终过滤。
        allowed = {
            f["id"] for f in task.input_schema["fields"] if f["kind"] not in {"image", "video"}
        }
        values = {
            key: value
            for key, value in execution.input_values.items()
            if key in allowed and type(value) in {str, int, float, bool}
        }
    work = Work(
        id=body.id,
        owner_id=user_id,
        workflow_id=task.workflow_id,
        version_id=task.version_id,
        execution_id=execution.id,
        title=body.title.strip(),
        description=body.description.strip() or None,
        request_hash=request_hash,
        cover_artifact_id=body.cover_artifact_id,
        cover_frame_ms=body.cover_frame_ms or None,
        input_values=values,
    )
    db.add(work)
    try:
        db.flush()
        for position, artifact_id in enumerate(body.artifact_ids):
            db.add(WorkArtifact(work_id=work.id, artifact_id=artifact_id, position=position))
        db.commit()
    except IntegrityError:
        # 并发的同编号发布由主键拦下，按已保存的那一份应答。
        db.rollback()
        prior = _published_before(db, body.id, user_id, request_hash)
        if prior is None:
            raise HTTPException(409, "重复发布的内容不一致") from None
        return prior, False
    return work, True
