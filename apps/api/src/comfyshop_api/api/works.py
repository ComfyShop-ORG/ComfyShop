"""作品接口，管理已经选定的执行成品及其公开状态。"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select, tuple_

from comfyshop_api.core.categories import WorkflowCategoryFilter
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
    CoverUpdate,
    RecordedInput,
    TaskInputsRead,
    WorkCreate,
    WorkPage,
    WorkRead,
    ReplayRead,
)
from comfyshop_api.security import Config, CurrentUser, DB, MaybeSession, Writer, owned_record
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE
from comfyshop_api.services.media_records import artifact_read, asset_read
from comfyshop_api.services.media_responses import (
    THUMBNAIL_RESPONSES,
    original_response,
    thumbnail_response,
)
from comfyshop_api.services.works import (
    public_work_condition,
    publish_work,
    readable_work,
    readable_work_asset,
    readable_work_cover,
    restore_deleted_work,
    update_work_cover,
    work_assets,
    work_reads,
)
from comfyshop_api.services.workflows import replay_workflow_read

router = APIRouter(prefix="/works", tags=["works"])


# `artifact_ids` 只选本人这次成功执行的成品，未选中的图片可单独作封面。封面是视频时可用
# `cover_frame_ms` 指定取哪一刻的画面，时间超出视频长度返回 422。
# `share_parameters` 公开标量输入，`share_assets` 公开整套输入。相同发布编号和内容可重试。
@router.post("", response_model=WorkRead, status_code=201)
def create_work(
    body: WorkCreate, db: DB, user: Writer, response: Response, config: Config
) -> WorkRead:
    work, created = publish_work(db, user.id, body, config)
    if not created:
        response.status_code = 200
    return work_reads(db, [work])[0]


# author 按作者账号名筛选，用于作者页面。
@router.get("", response_model=WorkPage)
def list_works(
    db: DB,
    session: MaybeSession,
    scope: Literal["public", "mine"] = "public",
    category: WorkflowCategoryFilter = "all",
    workflow_id: str | None = None,
    version_id: str | None = None,
    current_version_only: bool = False,
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
    if category != "all":
        query = query.where(Workflow.in_category(category))
    if workflow_id:
        query = query.where(Work.workflow_id == workflow_id)
    if version_id:
        query = query.where(Work.version_id == version_id)
    if current_version_only:
        query = query.where(Work.version_id == Workflow.published_version_id)
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


@router.put("/{work_id}/cover", response_model=WorkRead)
def set_work_cover(
    work_id: str, body: CoverUpdate, db: DB, user: Writer, config: Config
) -> WorkRead:
    work = update_work_cover(db, work_id, user.id, body, config)
    db.commit()
    return work_reads(db, [work])[0]


@router.get(
    "/{work_id}/cover/{sha256}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES
)
async def work_cover_thumbnail(
    work_id: str,
    sha256: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: int | None = Query(default=None, ge=1, le=MAX_THUMBNAIL_SIZE),
) -> Response:
    media = await run_in_threadpool(
        readable_work_cover, db, work_id, session.user_id if session else None, sha256
    )
    return await thumbnail_response(request, media, config, size)


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


# 作者发布时选择公开的参数、字段名称和参考素材。
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
        assets=[asset_read(asset) for asset in work_assets(db, work.id)],
    )


@router.get("/{work_id}/assets/{asset_id}/file", response_class=FileResponse)
def work_asset_file(
    work_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    download: bool = False,
) -> Response:
    asset = readable_work_asset(db, work_id, asset_id, session.user_id if session else None)
    return original_response(request, config.media_storage, asset.media, asset.filename, download)


@router.get(
    "/{work_id}/assets/{asset_id}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES
)
async def work_asset_thumbnail(
    work_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: int | None = Query(default=None, ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素"),
) -> Response:
    asset = await run_in_threadpool(
        readable_work_asset, db, work_id, asset_id, session.user_id if session else None
    )
    return await thumbnail_response(request, asset.media, config, size)


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
