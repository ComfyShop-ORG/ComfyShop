"""输入素材的去重、配额与回收。

素材被任务引用时保留，任务记录及其全部成品删除后，素材随之释放：不再计入配额，
过了保留期由后台删除。保留期也给删除后的撤销留出时间。
"""

from fastapi import HTTPException
from sqlalchemy import ColumnElement, delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import QueryableAttribute, Session

from comfyshop_api.core.config import Settings
from comfyshop_api.db import write_lock
from comfyshop_api.models import Artifact, Asset, MediaObject, Task, TaskAsset, User, now_ms
from comfyshop_api.services.originals import attach_original
from comfyshop_media.uploads import ReceivedMedia


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


QUOTA_FULL = "素材存储空间不足，删除不再需要的任务后可释放它们引用的素材"


def _released() -> ColumnElement[bool]:
    """与 `Asset` 关联的条件：被任务引用过，但引用它的任务和成品都已删除。"""
    return exists().where(TaskAsset.asset_id == Asset.id) & ~_kept(now_ms())


def _used(db: Session, owner_id: str) -> int:
    """账号计入配额的素材总量。已释放的素材不计入，文件留到保留期后清理。"""
    used = db.scalar(
        select(func.coalesce(func.sum(MediaObject.size), 0))
        .select_from(Asset)
        .join(Asset.media)
        .where(Asset.owner_id == owner_id, ~_released())
    )
    return used or 0


def ensure_quota_for_reuse(db: Session, owner_id: str, asset_ids: list[str], quota: int) -> None:
    """重新使用已释放的素材（再次上传相同文件或在新任务里引用）时，它要重新占用配额。

    放回后超出 `quota` 返回 413。仍计入配额的素材不受影响。
    """
    revived = db.scalar(
        select(func.coalesce(func.sum(MediaObject.size), 0))
        .select_from(Asset)
        .join(Asset.media)
        .where(Asset.id.in_(asset_ids), Asset.owner_id == owner_id, _released())
    )
    if revived and _used(db, owner_id) + revived > quota:
        raise HTTPException(413, QUOTA_FULL)


def ensure_quota_for_restore(db: Session, owner_id: str, task_id: str, quota: int) -> None:
    """撤销删除任务或它的成品之前调用：任务的素材若已释放，恢复后要重新占用配额。

    取得账号写锁，与上传和提交串行，锁保持到调用方提交。放回后超出 `quota` 返回 413。
    """
    write_lock(db, User, owner_id)
    asset_ids = list(db.scalars(select(TaskAsset.asset_id).where(TaskAsset.task_id == task_id)))
    if asset_ids:
        ensure_quota_for_reuse(db, owner_id, asset_ids, quota)


def store_asset(
    db: Session,
    owner_id: str,
    asset_id: str,
    filename: str,
    media: ReceivedMedia,
    config: Settings,
    stored: bool,
) -> Asset:
    """在账号写锁内登记刚接收的文件并提交，返回对应的素材。

    同一 `asset_id` 的重试返回原素材，内容不同返回 409。账号已有相同内容的素材时返回那份
    素材，并从现在重新计算它的保留期。
    已释放的素材不计入配额，其余素材的总量超出配额返回 413。拿回一份已释放的素材同样
    要占用配额。
    """
    prior = db.get(Asset, asset_id)
    if prior:
        if prior.owner_id != owner_id:
            raise HTTPException(404, "素材不存在")
        if prior.sha256 != media.sha256:
            raise HTTPException(409, "重复上传的文件不一致")
        return prior
    same = db.scalar(
        select(Asset)
        .where(Asset.owner_id == owner_id, Asset.sha256 == media.sha256)
        .order_by(Asset.created_at.desc(), Asset.id)
        .limit(1)
        .with_for_update(of=Asset)
    )
    if same:
        ensure_quota_for_reuse(db, owner_id, [same.id], config.asset_quota_bytes)
        same.created_at = now_ms()
        db.commit()
        return same
    if _used(db, owner_id) + media.size > config.asset_quota_bytes:
        raise HTTPException(413, QUOTA_FULL)
    asset = Asset(
        id=asset_id,
        owner_id=owner_id,
        filename=filename,
        media=attach_original(db, media, stored),
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.get(Asset, asset_id)
        if prior and prior.owner_id == owner_id and prior.sha256 == media.sha256:
            return prior
        raise HTTPException(409, "素材已存在") from None
    return asset


def remove_asset(db: Session, asset: Asset) -> None:
    """删除未被任务引用的素材。"""
    try:
        removed = db.scalar(
            delete(Asset)
            .where(Asset.id == asset.id, ~exists().where(TaskAsset.asset_id == Asset.id))
            .returning(Asset.id)
        )
        if not removed:
            raise HTTPException(409, "素材已被任务引用")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "素材已被任务引用") from None


def expire_unused_assets(db: Session, config: Settings) -> None:
    """删除超过保留期的素材：从未被任务使用，或引用它的任务及成品都已删除。"""
    cutoff = now_ms() - config.unused_asset_ttl_seconds * 1000
    released = select(Asset.id).where(Asset.created_at <= cutoff, ~_kept(cutoff))
    candidates = released.order_by(Asset.created_at, Asset.id).limit(100)
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
                    # 选出之后刚被重新上传的素材刷新了保留期，这里重新核对。
                    Asset.created_at <= cutoff,
                    ~exists().where(TaskAsset.asset_id == Asset.id),
                )
            )
            db.commit()
    except IntegrityError:
        db.rollback()
