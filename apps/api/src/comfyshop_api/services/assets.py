"""输入素材的去重、配额、资产库与回收。

资产库中的素材计入配额并持续保留。其他素材按任务引用与保留期回收。
"""

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Select, delete, exists, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import QueryableAttribute, Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Artifact,
    Asset,
    MediaObject,
    ProjectAsset,
    Task,
    TaskAsset,
    Team,
    User,
    WorkAsset,
    new_id,
    now_ms,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import AssetPage, AssetUsage, InputMediaKind
from comfyshop_api.security import workspace_records
from comfyshop_api.services.executions import task_has_results
from comfyshop_api.services.machines import WorkerIdentity, fence
from comfyshop_api.services.media_records import asset_read, media_kind
from comfyshop_api.services.originals import attach_original
from comfyshop_api.services.teams import TeamAccess
from comfyshop_api.services.workspace_shares import can_read_workspace_media
from comfyshop_media.model_exports import MODEL_DOWNLOAD_CONTENT_TYPES
from comfyshop_media.uploads import ASSET_UPLOAD_CONTENT_TYPES, ReceivedMedia


def _kept(since: int) -> ColumnElement[bool]:
    """与 `Asset` 关联的条件：引用它的某个任务或任务的成品没有在 `since` 之前删除。"""

    def standing(column: QueryableAttribute[int | None]) -> ColumnElement[bool]:
        return column.is_(None) | (column > since)

    return exists().where(
        TaskAsset.asset_id == Asset.id,
        TaskAsset.task_id == Task.id,
        standing(Task.deleted_at)
        | exists().where(Artifact.task_id == Task.id, standing(Artifact.deleted_at)),
    )


QUOTA_FULL = msg("asset.assetStorageIsFullDeleteUnused")


def _released() -> ColumnElement[bool]:
    """资产库以外，被任务引用过且相应任务和成品都已删除的素材。"""
    return (
        Asset.saved_at.is_(None) & exists().where(TaskAsset.asset_id == Asset.id) & ~_kept(now_ms())
    )


def asset_scope(owner_id: str, team_id: str | None) -> ColumnElement[bool]:
    return workspace_records(Asset.owner_id, Asset.team_id, owner_id, team_id)


def asset_in_scope(asset: Asset, owner_id: str, team_id: str | None) -> bool:
    return asset.team_id == team_id and (team_id is not None or asset.owner_id == owner_id)


def _charged_originals(owner_id: str, team_id: str | None) -> Select[tuple[str]]:
    return select(Asset.sha256).where(asset_scope(owner_id, team_id), ~_released())


def _used(db: Session, owner_id: str, team_id: str | None) -> int:
    """按原件累计空间用量。已释放的素材留到保留期后清理。"""
    used = db.scalar(
        select(func.coalesce(func.sum(MediaObject.size), 0)).where(
            MediaObject.sha256.in_(_charged_originals(owner_id, team_id))
        )
    )
    return used or 0


def _ensure_quota_for_original(
    db: Session, owner_id: str, sha256: str, size: int, quota: int, team_id: str | None
) -> None:
    """在登记素材之前，只对尚未计入空间用量的原件校验新增容量。"""
    charged = db.scalar(
        _charged_originals(owner_id, team_id).where(Asset.sha256 == sha256).limit(1)
    )
    if charged is None and _used(db, owner_id, team_id) + size > quota:
        raise HTTPException(413, QUOTA_FULL)


def asset_usage(
    db: Session, owner_id: str, config: Settings, *, team_id: str | None = None
) -> AssetUsage:
    used = _used(db, owner_id, team_id)
    quota = config.asset_quota_for(team_id)
    return AssetUsage(used_bytes=used, remaining_bytes=max(0, quota - used), limit_bytes=quota)


def ensure_quota_for_reuse(
    db: Session,
    owner_id: str,
    asset_ids: list[str],
    quota: int,
    *,
    team_id: str | None = None,
) -> None:
    """重新使用已释放的素材（再次上传相同文件或在新任务里引用）时，它要重新占用配额。

    放回后超出 `quota` 返回 413。
    """
    if not asset_ids:
        return
    requested = select(Asset.sha256).where(Asset.id.in_(asset_ids), asset_scope(owner_id, team_id))
    revived = db.scalar(
        select(func.coalesce(func.sum(MediaObject.size), 0)).where(
            MediaObject.sha256.in_(requested),
            MediaObject.sha256.not_in(_charged_originals(owner_id, team_id)),
        )
    )
    if revived and _used(db, owner_id, team_id) + revived > quota:
        raise HTTPException(413, QUOTA_FULL)


def ensure_quota_for_restore(db: Session, task: Task, config: Settings) -> None:
    """撤销删除任务或它的成品之前调用：任务的素材若已释放，恢复后要重新占用配额。

    取得空间写锁，与上传和提交串行。放回后超出 `quota` 返回 413。
    """
    if task.team_id is None:
        write_lock(db, User, task.owner_id)
    else:
        write_lock(db, Team, task.team_id)
    asset_ids = list(db.scalars(select(TaskAsset.asset_id).where(TaskAsset.task_id == task.id)))
    if asset_ids:
        ensure_quota_for_reuse(
            db, task.owner_id, asset_ids, config.asset_quota_for(task.team_id), team_id=task.team_id
        )


def _matching_asset(
    db: Session, owner_id: str, sha256: str, content_type: str, team_id: str | None
) -> Asset | None:
    return db.scalar(
        select(Asset)
        .where(
            asset_scope(owner_id, team_id),
            Asset.sha256 == sha256,
            Asset.content_type == content_type,
        )
        .order_by(Asset.created_at.desc(), Asset.id)
        .limit(1)
        .with_for_update(of=Asset)
    )


def reuse_original_as_asset(
    db: Session,
    owner_id: str,
    source: Asset | Artifact | WorkAsset,
    config: Settings,
    *,
    team_id: str | None = None,
) -> tuple[Asset, bool]:
    """在目标空间写锁内复用原件，返回空间中的素材及是否新建。"""
    existing = _matching_asset(db, owner_id, source.sha256, source.content_type, team_id)
    if existing:
        return existing, False
    _ensure_quota_for_original(
        db, owner_id, source.sha256, source.media.size, config.asset_quota_for(team_id), team_id
    )
    asset = Asset(
        id=new_id(),
        owner_id=owner_id,
        team_id=team_id,
        filename=source.filename,
        sha256=source.sha256,
        content_type=source.content_type,
    )
    db.add(asset)
    return asset, True


def list_library(
    db: Session,
    owner_id: str,
    kind: InputMediaKind | None,
    content_types: list[str] | None,
    search: str | None,
    cursor: str | None,
    limit: int,
    *,
    team_id: str | None = None,
    project_id: str | None = None,
) -> AssetPage:
    query = select(Asset).where(asset_scope(owner_id, team_id), Asset.saved_at.is_not(None))
    if project_id:
        query = query.where(
            Asset.id.in_(select(ProjectAsset.asset_id).where(ProjectAsset.project_id == project_id))
        )
    if kind is not None or content_types is not None:
        allowed = (
            ASSET_UPLOAD_CONTENT_TYPES
            if content_types is None
            else ASSET_UPLOAD_CONTENT_TYPES.intersection(content_types)
        )
        query = query.where(
            Asset.content_type.in_(
                [mime for mime in allowed if not kind or media_kind(mime) == kind]
            )
        )
    if search and (text := search.strip()):
        query = query.where(Asset.filename.icontains(text, autoescape=True))
    if position := decode_cursor(cursor, 2):
        query = query.where(tuple_(Asset.saved_at, Asset.id) < tuple(position))
    rows = db.scalars(query.order_by(Asset.saved_at.desc(), Asset.id.desc()).limit(limit + 1)).all()
    items, next_cursor = split_page(rows, limit, lambda asset: (asset.saved_at or 0, asset.id))
    return AssetPage(items=[asset_read(asset) for asset in items], next_cursor=next_cursor)


def readable_asset(db: Session, asset_id: str, viewer_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or not can_read_workspace_media(db, asset.owner_id, viewer_id, asset.team_id):
        raise HTTPException(404, msg("asset.notFound"))
    if asset.owner_id == viewer_id or asset.saved_at is not None:
        return asset
    attached = (
        select(Task.id)
        .join(TaskAsset, TaskAsset.task_id == Task.id)
        .where(
            TaskAsset.asset_id == asset.id,
            workspace_records(Task.owner_id, Task.team_id, asset.owner_id, asset.team_id),
            Task.visible() | task_has_results(Task.id),
        )
        .exists()
    )
    if db.scalar(select(attached)):
        return asset
    raise HTTPException(404, msg("asset.notFound"))


def save_library_asset(db: Session, asset: Asset, config: Settings) -> Asset:
    """在空间写锁内保存已登记的素材。重复保存保留原来的排序位置。"""
    if asset.saved_at is None:
        ensure_quota_for_reuse(
            db,
            asset.owner_id,
            [asset.id],
            config.asset_quota_for(asset.team_id),
            team_id=asset.team_id,
        )
        asset.saved_at = now_ms()
    db.commit()
    return asset


def save_artifact_as_asset(
    db: Session,
    artifact: Artifact,
    user_id: str,
    config: Settings,
    *,
    team: TeamAccess | None = None,
    save_to_library: bool = True,
) -> Asset:
    """用已验证的成品原件登记素材，沿用输入素材的格式、文件大小及账号配额。"""
    if artifact.content_type not in ASSET_UPLOAD_CONTENT_TYPES:
        raise HTTPException(422, msg("asset.outputFormatNotSupported"))
    if artifact.media.size > config.max_asset_bytes:
        raise HTTPException(413, msg("media.theFileIsTooLarge"))
    asset, created = reuse_original_as_asset(
        db, user_id, artifact, config, team_id=team.team.id if team else None
    )
    if not save_to_library:
        if not created:
            asset.created_at = now_ms()
            ensure_quota_for_reuse(
                db,
                user_id,
                [asset.id],
                config.asset_quota_for(asset.team_id),
                team_id=asset.team_id,
            )
        if team and created:
            team.record(db, "asset.uploaded", asset.id)
        db.commit()
        return asset
    if team and asset.saved_at is None:
        team.record(db, "asset.savedFromResult", asset.id)
    return save_library_asset(db, asset, config)


def copy_asset_to_team(db: Session, source: Asset, team: TeamAccess, config: Settings) -> Asset:
    if source.media.size > config.max_asset_bytes:
        raise HTTPException(413, msg("media.theFileIsTooLarge"))
    asset, created = reuse_original_as_asset(
        db, team.actor_id, source, config, team_id=team.team.id
    )
    if created:
        team.record(db, "asset.copied", asset.id)
    return save_library_asset(db, asset, config)


def leased_task_asset(
    db: Session, task_id: str, asset_id: str, machine: WorkerIdentity, lease: str | None
) -> Asset:
    task = fence(db, task_id, machine, lease)
    asset = db.scalar(
        select(Asset)
        .join(TaskAsset)
        .where(
            TaskAsset.task_id == task.id,
            Asset.id == asset_id,
            asset_scope(task.owner_id, task.team_id),
        )
    )
    if asset is None:
        raise HTTPException(404, msg("asset.notFound"))
    return asset


def store_asset(
    db: Session,
    owner_id: str,
    asset_id: str,
    filename: str,
    media: ReceivedMedia,
    config: Settings,
    stored: bool,
    *,
    save_to_library: bool = False,
    team: TeamAccess | None = None,
) -> Asset:
    """在账号写锁内登记刚接收的文件并提交，返回对应的素材。

    同一 `asset_id` 的重试返回原素材，字节或 MIME 不同返回 409。账号已有相同字节和 MIME
    的素材时返回那份素材，并从现在重新计算它的保留期。
    已释放的素材不计入配额，其余素材的总量超出配额返回 413。拿回一份已释放的素材同样
    要占用配额。
    """
    if media.content_type in MODEL_DOWNLOAD_CONTENT_TYPES:
        raise HTTPException(400, msg("media.theFileIsNotAValid"))
    team_id = team.team.id if team else None
    quota = config.asset_quota_for(team_id)
    prior = db.get(Asset, asset_id, with_for_update={"of": Asset})
    if prior:
        if not asset_in_scope(prior, owner_id, team_id):
            raise HTTPException(404, msg("asset.notFound"))
        if prior.sha256 != media.sha256 or prior.content_type != media.content_type:
            raise HTTPException(409, msg("output.theFileDiffersFromAnEarlier"))
        return save_library_asset(db, prior, config) if save_to_library else prior
    same = _matching_asset(db, owner_id, media.sha256, media.content_type, team_id)
    if same:
        same.created_at = now_ms()
        if save_to_library:
            return save_library_asset(db, same, config)
        ensure_quota_for_reuse(db, owner_id, [same.id], quota, team_id=team_id)
        db.commit()
        return same
    _ensure_quota_for_original(db, owner_id, media.sha256, media.size, quota, team_id)
    asset = Asset(
        id=asset_id,
        owner_id=owner_id,
        team_id=team_id,
        filename=filename,
        content_type=media.content_type,
        media=attach_original(db, media, stored),
        saved_at=now_ms() if save_to_library else None,
    )
    db.add(asset)
    if team is not None:
        team.record(db, "asset.uploaded", asset.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.get(Asset, asset_id)
        if (
            prior
            and asset_in_scope(prior, owner_id, team_id)
            and prior.sha256 == media.sha256
            and prior.content_type == media.content_type
            and (not save_to_library or prior.saved_at is not None)
        ):
            return prior
        raise HTTPException(409, msg("asset.thisAssetAlreadyExists")) from None
    return asset


def _delete_unbound_asset(db: Session, asset_id: str) -> str | None:
    return db.scalar(
        delete(Asset)
        .where(Asset.id == asset_id, ~exists().where(TaskAsset.asset_id == Asset.id))
        .returning(Asset.id)
    )


def remove_asset(db: Session, asset: Asset) -> None:
    """删除未被任务引用的素材。"""
    try:
        if not _delete_unbound_asset(db, asset.id):
            raise HTTPException(409, msg("asset.thisAssetIsUsedByA"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("asset.thisAssetIsUsedByA")) from None


def remove_library_asset(db: Session, asset: Asset) -> None:
    """移出资产库。任务仍在引用时，交回任务的素材保留规则处理。"""
    if asset.saved_at is not None and not _delete_unbound_asset(db, asset.id):
        db.execute(delete(ProjectAsset).where(ProjectAsset.asset_id == asset.id))
        asset.saved_at = None
    db.commit()


def expire_unused_assets(db: Session, config: Settings) -> None:
    """清理超过保留期且未被资产库或任务保留的素材。"""
    cutoff = now_ms() - config.unused_asset_ttl_seconds * 1000
    released = select(Asset.id).where(
        Asset.saved_at.is_(None), Asset.created_at <= cutoff, ~_kept(cutoff)
    )
    candidates = (
        released.order_by(Asset.created_at, Asset.id)
        .limit(100)
        .with_for_update(of=Asset, skip_locked=True)
    )
    try:
        ids = list(db.scalars(candidates))
        if ids:
            # 素材及其任务引用在同一事务内变更。
            db.execute(
                delete(TaskAsset).where(TaskAsset.asset_id.in_(released.where(Asset.id.in_(ids))))
            )
            db.execute(
                delete(Asset).where(
                    Asset.id.in_(ids),
                    # 重新核对选出之后保存到资产库或再次上传的素材。
                    Asset.saved_at.is_(None),
                    Asset.created_at <= cutoff,
                    ~exists().where(TaskAsset.asset_id == Asset.id),
                )
            )
            db.commit()
    except IntegrityError:
        db.rollback()
