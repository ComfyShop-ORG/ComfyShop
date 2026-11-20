"""处理工作机成品回传与成品的读取授权。上传、预览和下载共享成品记录。"""

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from comfyshop_api.models import LoginSession, Status, Artifact, Execution, Task
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.core.config import Settings
from comfyshop_api.schemas import MAX_COVER_FRAME_MS, ArtifactPage, ArtifactRead, ExecutionRead
from comfyshop_api.security import Config, CurrentUser, DB, MaybeSession, Writer, owned_record
from comfyshop_api.services.artifacts import (
    lock_execution_media,
    ArtifactUpload,
    begin_artifact_upload,
    delete_result_artifacts,
    is_cover_frame,
    record_artifact,
)
from comfyshop_api.services.assets import ensure_quota_for_restore
from comfyshop_api.services.media_records import artifact_read, detach_media_record
from comfyshop_api.services.media_responses import (
    THUMBNAIL_RESPONSES,
    original_response,
    thumbnail_response,
    video_preview_response,
)
from comfyshop_api.services.media_uploads import upload_media
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE, MAX_VIDEO_PREVIEW_SIZE
from comfyshop_media.uploads import ReceivedMedia
from comfyshop_api.services.machines import CurrentMachine, Lease, fence
from comfyshop_api.services.executions import execution_reads, owned_execution
from comfyshop_api.services.works import artifact_public

router = APIRouter(tags=["artifacts"])


@router.put(
    "/worker/tasks/{task_id}/artifacts/{client_id}",
    response_model=ArtifactRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_artifact(
    task_id: str,
    client_id: str,
    request: Request,
    db: DB,
    machine: CurrentMachine,
    config: Config,
    filename: str = Query(min_length=1, max_length=200),
    sha256: str = Query(pattern=r"^[a-f0-9]{64}$"),
    execution_index: int = Query(ge=0, le=31),
    output_node_id: str = Query(min_length=1, max_length=120),
    output_slot: str = Query(min_length=1, max_length=256),
    output_index: int = Query(ge=0, le=1023),
    x_task_lease: Lease = None,
) -> ArtifactRead:
    # 每个输出显式绑定执行序号、节点、输出槽和顺序。相同回传编号可安全重试同一文件。
    if not client_id or len(client_id) > 64 or not all(c.isalnum() or c in "_-" for c in client_id):
        raise HTTPException(422, "成品编号无效")
    upload = ArtifactUpload(
        client_id, sha256, execution_index, output_node_id, output_slot, output_index
    )

    # 数据库访问放到线程里：SQLite 等写锁时会阻塞，不能卡住处理全部请求的事件循环。
    def begin() -> ArtifactRead | str:
        task = fence(db, task_id, machine, x_task_lease, terminal=True)
        target = begin_artifact_upload(db, task, upload)
        if isinstance(target, Artifact):
            return artifact_read(target, task)
        # Release the read transaction while a potentially large file arrives.
        db.rollback()
        return target

    node_title = await run_in_threadpool(begin)
    if isinstance(node_title, ArtifactRead):
        return node_title

    def record(media: ReceivedMedia, stored: bool) -> tuple[ArtifactRead, bool]:
        try:
            artifact, task = record_artifact(
                db,
                task_id,
                machine,
                x_task_lease,
                upload,
                filename,
                node_title,
                media,
                config.max_execution_artifacts,
                stored,
            )
            return artifact_read(artifact, task), artifact.media.storage_name == media.path.name
        except BaseException:
            # 立即释放写锁，不等请求结束时关闭会话。
            db.rollback()
            raise

    return await upload_media(request, db, config, config.max_artifact_bytes, record, sha256)


@router.get("/artifacts", response_model=ArtifactPage)
def list_artifacts(
    db: DB,
    user: CurrentUser,
    workflow_id: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
) -> ArtifactPage:
    query = (
        select(Artifact, Task)
        .join(Task)
        .join(Execution, Execution.id == Artifact.execution_id)
        .where(
            Artifact.owner_id == user.id,
            Artifact.visible(),
            Execution.status == Status.SUCCEEDED,
        )
    )
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if task_id:
        query = query.where(Task.id == task_id)
    if execution_id:
        owned_execution(db, execution_id, user.id)
        query = query.where(Artifact.execution_id == execution_id)
    position = decode_cursor(cursor, 2)
    if position:
        query = (
            query.where(tuple_(Artifact.output_index, Artifact.id) > tuple(position))
            if execution_id
            else query.where(tuple_(Artifact.created_at, Artifact.id) < tuple(position))
        )
    records = db.execute(
        (
            query.order_by(Artifact.output_index, Artifact.id)
            if execution_id
            else query.order_by(Artifact.created_at.desc(), Artifact.id.desc())
        ).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(
        records,
        limit,
        lambda row: (row[0].output_index if execution_id else row[0].created_at, row[0].id),
    )
    return ArtifactPage(items=[artifact_read(a, t) for a, t in items], next_cursor=next_cursor)


@router.delete("/artifacts/{artifact_id}", response_model=ExecutionRead)
def delete_artifact(artifact_id: str, db: DB, user: Writer) -> ExecutionRead:
    artifact = owned_record(db, Artifact, artifact_id, user.id, "成品不存在")
    execution, task = owned_execution(db, artifact.execution_id, user.id)
    delete_result_artifacts(db, execution, artifact.id)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


# 撤销删除单份成品，返回所属执行的最新资料。
@router.post("/artifacts/{artifact_id}/restore", response_model=ExecutionRead)
def restore_artifact(artifact_id: str, db: DB, user: Writer, config: Config) -> ExecutionRead:
    artifact = owned_record(db, Artifact, artifact_id, user.id, "成品不存在")
    execution, task = owned_execution(db, artifact.execution_id, user.id)
    # 已删除任务的成品恢复后，任务的素材重新计入配额。
    ensure_quota_for_restore(db, user.id, task.id, config.asset_quota_bytes)
    lock_execution_media(db, execution.id)
    db.refresh(artifact)
    if artifact.restore():
        db.commit()
    return execution_reads(db, [(execution, task)])[0]


def readable_artifact(artifact_id: str, db: Session, session: LoginSession | None) -> Artifact:
    """返回已成功执行且对当前访问者开放的成品。无权读取与记录缺失都返回 404。"""
    artifact = db.get(Artifact, artifact_id)
    task = db.get(Task, artifact.task_id) if artifact else None
    execution = db.get(Execution, artifact.execution_id) if artifact else None
    if (
        not artifact
        or artifact.deleted_at is not None
        or not task
        or not execution
        or execution.status != Status.SUCCEEDED
        or (
            (not session or session.user_id != artifact.owner_id)
            and not artifact_public(db, artifact.id)
        )
    ):
        raise HTTPException(404, "成品不存在")
    return artifact


@router.get("/artifacts/{artifact_id}/file", response_class=FileResponse)
def artifact_file(
    artifact_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    download: bool = False,
) -> Response:
    artifact = _detached_artifact(artifact_id, db, session)
    return original_response(
        request, config.media_storage, artifact.media, artifact.filename, download
    )


@router.get(
    "/artifacts/{artifact_id}/thumbnail",
    response_class=Response,
    responses=THUMBNAIL_RESPONSES,
)
async def artifact_thumbnail(
    artifact_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: int | None = Query(default=None, ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素"),
):
    return await _thumbnail(artifact_id, request, db, session, config, size, 0)


# 被选作封面的视频画面。`frame_ms` 须是某个结果组或作品为这份视频选定的时间点，
# 地址由封面的 `media` 给出，不能用来截取任意时刻。
@router.get(
    "/artifacts/{artifact_id}/frames/{frame_ms}/thumbnail",
    response_class=Response,
    responses=THUMBNAIL_RESPONSES,
)
async def artifact_frame_thumbnail(
    artifact_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    frame_ms: int = Path(ge=1, le=MAX_COVER_FRAME_MS, description="视频画面的时间点，毫秒"),
    size: int | None = Query(default=None, ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素"),
):
    return await _thumbnail(artifact_id, request, db, session, config, size, frame_ms)


async def _thumbnail(
    artifact_id: str,
    request: Request,
    db: Session,
    session: LoginSession | None,
    config: Settings,
    size: int | None,
    frame_ms: int,
) -> Response:
    artifact = await run_in_threadpool(_detached_artifact, artifact_id, db, session, frame_ms)
    return await thumbnail_response(request, artifact.media, config, size, frame_ms)


def _detached_artifact(
    artifact_id: str, db: Session, session: LoginSession | None, frame_ms: int = 0
) -> Artifact:
    """核对读取授权后返回脱离会话的成品，并结束读事务，生成缩略图期间不占用数据库。

    `frame_ms` 大于 0 时，这一刻的画面还须是选定的封面，否则返回 404。
    """
    artifact = readable_artifact(artifact_id, db, session)
    if frame_ms and not is_cover_frame(db, artifact.id, frame_ms):
        raise HTTPException(404, "成品不存在")
    detach_media_record(db, artifact)
    return artifact


@router.get(
    "/artifacts/{artifact_id}/video-preview",
    response_class=FileResponse,
    responses={
        status: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}}
        for status in (200, 206)
    },
)
async def artifact_video_preview(
    artifact_id: str,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: int = Query(ge=1, le=MAX_VIDEO_PREVIEW_SIZE, description="目标长边像素"),
) -> Response:
    artifact = await run_in_threadpool(_detached_artifact, artifact_id, db, session)
    return await video_preview_response(artifact.media, config, size)
