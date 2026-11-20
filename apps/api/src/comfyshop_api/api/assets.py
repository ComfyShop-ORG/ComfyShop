"""管理用户的私有输入素材，工作机只能下载当前租约任务已绑定的素材。"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from comfyshop_api.db import write_lock
from comfyshop_api.models import Asset, TaskAsset, User
from comfyshop_api.schemas import AssetRead
from comfyshop_api.security import Config, CurrentUser, DB, Writer, owned_record
from comfyshop_api.services.machines import CurrentMachine, Lease, fence
from comfyshop_api.services.assets import remove_asset, store_asset
from comfyshop_api.services.media_records import asset_read, detach_media_record
from comfyshop_api.services.media_responses import (
    THUMBNAIL_RESPONSES,
    original_response,
    thumbnail_response,
)
from comfyshop_api.services.media_uploads import upload_media
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE
from comfyshop_media.uploads import ReceivedMedia

router = APIRouter(tags=["assets"])


@router.put(
    "/assets/{asset_id}",
    response_model=AssetRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_asset(
    asset_id: UUID,
    request: Request,
    db: DB,
    user: Writer,
    config: Config,
    filename: str = Query(min_length=1, max_length=200),
) -> AssetRead:
    # asset_id 由浏览器生成并在上传重试中复用。同 ID 的不同内容返回 409。
    # 账号已有相同内容时返回原有素材，客户端使用响应里的 ID。
    # 数据库访问放到线程里：SQLite 等写锁时会阻塞，不能卡住处理全部请求的事件循环。
    owner_id = user.id

    def check_owner() -> None:
        prior = db.get(Asset, str(asset_id))
        if prior and prior.owner_id != owner_id:
            raise HTTPException(404, "素材不存在")
        db.rollback()

    def store(media: ReceivedMedia, stored: bool) -> tuple[AssetRead, bool]:
        try:
            # Serialize quota checks for uploads belonging to the same account.
            write_lock(db, User, owner_id)
            name = Path(filename.replace("\\", "/")).name or "media"
            asset = store_asset(db, owner_id, str(asset_id), name, media, config, stored)
            return asset_read(asset), asset.media.storage_name == media.path.name
        except BaseException:
            # 立即释放写锁，不等请求结束时关闭会话。
            db.rollback()
            raise

    await run_in_threadpool(check_owner)
    return await upload_media(request, db, config, config.max_asset_bytes, store)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, db: DB, user: Writer) -> None:
    asset = owned_record(db, Asset, asset_id, user.id, "素材不存在")
    remove_asset(db, asset)


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: str, db: DB, user: CurrentUser) -> AssetRead:
    asset = owned_record(db, Asset, asset_id, user.id, "素材不存在")
    return asset_read(asset)


@router.get("/assets/{asset_id}/file", response_class=FileResponse)
def get_asset_file(
    asset_id: str, request: Request, db: DB, user: CurrentUser, config: Config
) -> Response:
    asset = _owned_asset_for_read(db, asset_id, user.id)
    return original_response(request, config.media_storage, asset.media, asset.filename)


@router.get("/assets/{asset_id}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES)
async def get_asset_thumbnail(
    asset_id: str,
    request: Request,
    db: DB,
    user: CurrentUser,
    config: Config,
    size: int | None = Query(default=None, ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素"),
) -> Response:
    asset = await run_in_threadpool(_owned_asset_for_read, db, asset_id, user.id)
    return await thumbnail_response(request, asset.media, config, size)


def _owned_asset_for_read(db: Session, asset_id: str, owner_id: str) -> Asset:
    asset = owned_record(db, Asset, asset_id, owner_id, "素材不存在")
    detach_media_record(db, asset)
    return asset


@router.get("/worker/tasks/{task_id}/assets/{asset_id}", response_class=FileResponse)
def get_task_asset(
    task_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    machine: CurrentMachine,
    config: Config,
    x_task_lease: Lease = None,
) -> Response:
    task = fence(db, task_id, machine, x_task_lease)
    asset = db.scalar(
        select(Asset)
        .join(TaskAsset)
        .where(TaskAsset.task_id == task.id, Asset.id == asset_id, Asset.owner_id == task.owner_id)
    )
    if not asset:
        raise HTTPException(404, "素材不存在")
    detach_media_record(db, asset)
    return original_response(request, config.media_storage, asset.media, asset.filename)
