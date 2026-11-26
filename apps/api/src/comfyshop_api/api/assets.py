"""管理用户的私有输入素材，工作机只能下载当前租约任务已绑定的素材。"""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from comfyshop_api.api.teams import TeamEditor, TeamReader, team_editor
from comfyshop_api.api.workspace_shares import SignedInWorkspaceReader
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Asset, TeamRole, User
from comfyshop_api.schemas import AssetPage, AssetRead, AssetUsage, InputMediaKind
from comfyshop_api.security import (
    COOKIE_NAME,
    DB,
    Config,
    CurrentUser,
    LockedWriter,
    Writer,
    digest,
    lock_session_account,
    owned_record,
)
from comfyshop_api.services.assets import (
    asset_in_scope,
    asset_usage,
    copy_asset_to_team,
    leased_task_asset,
    list_library,
    readable_asset,
    remove_asset,
    remove_library_asset,
    save_library_asset,
    store_asset,
)
from comfyshop_api.services.machines import CurrentWorker, Lease
from comfyshop_api.services.media_records import asset_read, detach_media_record
from comfyshop_api.services.media_responses import (
    THUMBNAIL_RESPONSES,
    original_response,
    thumbnail_response,
)
from comfyshop_api.services.media_uploads import upload_media
from comfyshop_api.services.projects import scoped_project
from comfyshop_api.services.teams import require_team
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE
from comfyshop_media.uploads import ReceivedMedia

router = APIRouter(tags=["assets"])
ASSET_UPLOAD = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}
AssetFilename = Annotated[str, Query(min_length=1, max_length=200)]


@router.get("/assets")
def list_assets(
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    kind: InputMediaKind | None = None,
    content_types: Annotated[list[str] | None, Query(max_length=40)] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    project_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> AssetPage:
    team_id = team.team.id if team else None
    project = scoped_project(db, str(project_id), owner_id, team_id) if project_id else None
    return list_library(
        db,
        owner_id,
        kind,
        content_types,
        search,
        cursor,
        limit,
        team_id=team_id,
        project_id=project.id if project else None,
    )


@router.get("/assets/usage")
def get_asset_usage(
    db: DB, team: TeamReader, owner_id: SignedInWorkspaceReader, config: Config
) -> AssetUsage:
    return asset_usage(db, owner_id, config, team_id=team.team.id if team else None)


@router.put("/assets/{asset_id}", openapi_extra=ASSET_UPLOAD)
async def upload_asset(
    asset_id: UUID,
    request: Request,
    db: DB,
    user: Writer,
    config: Config,
    filename: AssetFilename,
    save_to_library: bool = False,
) -> AssetRead:
    return await receive_asset(asset_id, request, db, user, config, filename, save_to_library)


@router.put("/teams/{team_id}/assets/{asset_id}", openapi_extra=ASSET_UPLOAD)
async def upload_team_asset(
    team_id: UUID,
    asset_id: UUID,
    request: Request,
    db: DB,
    user: Writer,
    config: Config,
    filename: AssetFilename,
    save_to_library: bool = True,
) -> AssetRead:
    return await receive_asset(
        asset_id, request, db, user, config, filename, save_to_library, team_id=str(team_id)
    )


async def receive_asset(
    asset_id: UUID,
    request: Request,
    db: DB,
    user: User,
    config: Config,
    filename: str,
    save_to_library: bool,
    *,
    team_id: str | None = None,
) -> AssetRead:
    # asset_id 由浏览器生成并在上传重试中复用。同 ID 的不同字节或格式返回 409。
    # 账号已有相同字节和格式时返回原有素材，客户端使用响应里的 ID。
    # 数据库访问放到线程里：SQLite 等写锁时会阻塞，不能卡住处理全部请求的事件循环。
    owner_id = user.id
    session_hash = digest(request.cookies[COOKIE_NAME])
    name = Path(filename.replace("\\", "/")).name or "media"

    def check_owner() -> None:
        if team_id is not None:
            require_team(db, team_id, owner_id, minimum=TeamRole.EDITOR)
        prior = db.get(Asset, str(asset_id))
        if prior and not asset_in_scope(prior, owner_id, team_id):
            raise HTTPException(404, msg("asset.notFound"))
        db.rollback()

    def store(media: ReceivedMedia, stored: bool) -> tuple[AssetRead, bool]:
        try:
            lock_session_account(db, user, session_hash)
            team = (
                require_team(db, team_id, owner_id, minimum=TeamRole.EDITOR, locked=True)
                if team_id
                else None
            )
            asset = store_asset(
                db,
                owner_id,
                str(asset_id),
                name,
                media,
                config,
                stored,
                save_to_library=save_to_library,
                team=team,
            )
            return asset_read(asset), asset.media.storage_name == media.path.name
        except BaseException:
            # 立即释放写锁，不等请求结束时关闭会话。
            db.rollback()
            raise

    await run_in_threadpool(check_owner)
    return await upload_media(
        request,
        db,
        config,
        config.max_asset_bytes,
        store,
        source_filename=name,
    )


@router.post("/teams/{team_id}/assets/{asset_id}/copy", status_code=201)
def copy_team_asset(
    team_id: UUID, asset_id: str, db: DB, user: LockedWriter, config: Config
) -> AssetRead:
    team = team_editor(team_id, db, user)
    source = owned_record(
        db, Asset, asset_id, team.actor_id, msg("asset.notFound"), for_update=True
    )
    return asset_read(copy_asset_to_team(db, source, team, config))


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, db: DB, user: LockedWriter) -> None:
    asset = owned_record(db, Asset, asset_id, user.id, msg("asset.notFound"))
    remove_asset(db, asset)


@router.put("/assets/{asset_id}/library")
def save_asset(
    asset_id: str, db: DB, user: CurrentUser, team: TeamEditor, config: Config
) -> AssetRead:
    asset = owned_record(
        db,
        Asset,
        asset_id,
        user.id,
        msg("asset.notFound"),
        for_update=True,
        team_id=team.team.id if team else None,
    )
    if team and asset.saved_at is None:
        team.record(db, "asset.saved", asset.id)
    return asset_read(save_library_asset(db, asset, config))


@router.delete("/assets/{asset_id}/library", status_code=204)
def remove_saved_asset(asset_id: str, db: DB, user: CurrentUser, team: TeamEditor) -> None:
    asset = owned_record(
        db,
        Asset,
        asset_id,
        user.id,
        msg("asset.notFound"),
        for_update=True,
        team_id=team.team.id if team else None,
    )
    if team and asset.saved_at is not None:
        team.record(db, "asset.removed", asset.id)
    remove_library_asset(db, asset)


@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: str, db: DB, user: CurrentUser, team: TeamReader, owner_id: SignedInWorkspaceReader
) -> AssetRead:
    asset = readable_asset(db, asset_id, user.id)
    if not asset_in_scope(asset, owner_id, team.team.id if team else None):
        raise HTTPException(404, msg("asset.notFound"))
    return asset_read(asset)


@router.get("/assets/{asset_id}/file", response_class=FileResponse)
def get_asset_file(
    asset_id: str, request: Request, db: DB, user: CurrentUser, config: Config
) -> Response:
    asset = _asset_for_delivery(db, asset_id, user.id)
    return original_response(request, config.media_storage, asset)


@router.get("/assets/{asset_id}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES)
async def get_asset_thumbnail(
    asset_id: str,
    request: Request,
    db: DB,
    user: CurrentUser,
    config: Config,
    size: Annotated[
        int | None, Query(ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素")
    ] = None,
) -> Response:
    asset = await run_in_threadpool(_asset_for_delivery, db, asset_id, user.id)
    return await thumbnail_response(request, asset, config, size)


def _asset_for_delivery(db: Session, asset_id: str, viewer_id: str) -> Asset:
    asset = readable_asset(db, asset_id, viewer_id)
    detach_media_record(db, asset)
    return asset


@router.get("/worker/tasks/{task_id}/assets/{asset_id}", response_class=FileResponse)
def get_task_asset(
    task_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    machine: CurrentWorker,
    config: Config,
    x_task_lease: Lease = None,
) -> Response:
    asset = leased_task_asset(db, task_id, asset_id, machine, x_task_lease)
    detach_media_record(db, asset)
    return original_response(request, config.media_storage, asset)
