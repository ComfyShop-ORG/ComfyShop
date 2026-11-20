"""作品接口，管理已经选定的执行成品及其公开状态。"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select, tuple_

from comfyshop_api.models import (
    Artifact,
    Execution,
    Task,
    User,
    Work,
    WorkArtifact,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ArtifactPage,
    RecordedInput,
    TaskInputsRead,
    WorkCreate,
    WorkPage,
    WorkRead,
    ReplayRead,
)
from comfyshop_api.security import Config, CurrentUser, DB, MaybeSession, Writer, owned_record
from comfyshop_media.renditions import cover_frame
from comfyshop_api.services.media_records import artifact_read, media_source
from comfyshop_api.services.works import (
    public_work_condition,
    publish_work,
    readable_work,
    restore_deleted_work,
    work_reads,
)
from comfyshop_api.services.workflows import replay_workflow_read

router = APIRouter(prefix="/works", tags=["works"])


# `artifact_ids` 只选本人这次成功执行的成品，封面要在所选成品内。封面是视频时可用
# `cover_frame_ms` 指定取哪一刻的画面，时间超出视频长度返回 422。
# `share_parameters` 开启后只公开标量输入。相同发布编号和内容可安全重试。
@router.post("", response_model=WorkRead, status_code=201)
def create_work(body: WorkCreate, db: DB, user: Writer, response: Response, config: Config):
    if body.cover_frame_ms:
        # 截取画面可能要几秒，在发布取得写锁之前核对。封面是否属于这次执行由发布核对。
        cover = db.get(Artifact, body.cover_artifact_id)
        if cover and cover.owner_id == user.id:
            cover_frame(media_source(cover.media), config, body.cover_frame_ms)
        db.rollback()
    work, created = publish_work(db, user.id, body)
    if not created:
        response.status_code = 200
    return work_reads(db, [work])[0]


# author 按作者账号名筛选，用于作者页面。
@router.get("", response_model=WorkPage)
def list_works(
    db: DB,
    session: MaybeSession,
    scope: Literal["public", "mine"] = "public",
    workflow_id: str | None = None,
    author: str = Query(default="", max_length=32),
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
):
    query = select(Work).join(Workflow)
    if scope == "mine":
        if not session:
            raise HTTPException(401, "请先登录")
        query = query.where(Work.owner_id == session.user_id, Work.visible())
    else:
        query = query.where(public_work_condition())
    if workflow_id:
        query = query.where(Work.workflow_id == workflow_id)
    if author.strip():
        query = query.where(
            Work.owner_id.in_(select(User.id).where(User.username == author.strip()))
        )
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(Work.created_at, Work.id) < tuple(position))
    records = list(
        db.scalars(query.order_by(Work.created_at.desc(), Work.id.desc()).limit(limit + 1))
    )
    items, next_cursor = split_page(records, limit, lambda work: (work.created_at, work.id))
    return WorkPage(items=work_reads(db, list(items)), next_cursor=next_cursor)


@router.get("/{work_id}", response_model=WorkRead)
def get_work(work_id: str, db: DB, session: MaybeSession):
    return work_reads(db, [readable_work(db, work_id, session.user_id if session else None)])[0]


@router.get("/{work_id}/artifacts", response_model=ArtifactPage)
def work_artifacts(
    work_id: str,
    db: DB,
    session: MaybeSession,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
):
    work = readable_work(db, work_id, session.user_id if session else None)
    execution = db.get(Execution, work.execution_id)
    if execution is None:
        raise HTTPException(404, "执行不存在")
    task = db.get(Task, execution.task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    query = select(WorkArtifact, Artifact).join(Artifact).where(WorkArtifact.work_id == work.id)
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(WorkArtifact.position, Artifact.id) > tuple(position))
    records = db.execute(query.order_by(WorkArtifact.position, Artifact.id).limit(limit + 1)).all()
    items, next_cursor = split_page(records, limit, lambda row: (row[0].position, row[1].id))
    return ArtifactPage(items=[artifact_read(a, task) for _, a in items], next_cursor=next_cursor)


# 作者发布时选择公开的参数及其字段名称。参考素材不随作品公开，所以素材列表为空。
@router.get("/{work_id}/inputs", response_model=TaskInputsRead)
def work_inputs(work_id: str, db: DB, session: MaybeSession) -> TaskInputsRead:
    work = readable_work(db, work_id, session.user_id if session else None)
    execution = db.get(Execution, work.execution_id)
    task = db.get(Task, execution.task_id) if execution else None
    version = db.scalar(select(WorkflowVersion.number).where(WorkflowVersion.id == work.version_id))
    if task is None or version is None:
        raise HTTPException(404, "作品不存在")
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
            if field["id"] in work.input_values
        ],
        assets=[],
    )


@router.delete("/{work_id}", status_code=204)
def unpublish_work(work_id: str, db: DB, user: Writer):
    work = readable_work(db, work_id, user.id)
    if work.owner_id != user.id:
        raise HTTPException(404, "作品不存在")
    work.published = False
    db.commit()
    return Response(status_code=204)


# DELETE /works/{work_id} 已用于取消公开。单独提供删除记录的操作。
@router.post("/{work_id}/delete", status_code=204)
def delete_work(work_id: str, db: DB, user: Writer) -> Response:
    work = owned_record(db, Work, work_id, user.id, "作品不存在")
    if work.mark_deleted():
        db.commit()
    return Response(status_code=204)


# 撤销删除。作品恢复删除前的公开状态。
@router.post("/{work_id}/restore", status_code=204)
def restore_work(work_id: str, db: DB, user: Writer) -> Response:
    work = owned_record(db, Work, work_id, user.id, "作品不存在")
    restore_deleted_work(db, work)
    db.commit()
    return Response(status_code=204)


@router.get("/{work_id}/replay", response_model=ReplayRead)
def replay_work(work_id: str, db: DB, user: CurrentUser):
    work = readable_work(db, work_id, user.id)
    return ReplayRead(
        workflow=replay_workflow_read(db, work.workflow_id, work.version_id, user.id),
        source_work_id=work.id,
    )
