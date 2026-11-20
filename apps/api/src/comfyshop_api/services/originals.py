"""登记共享原件，并依据素材和成品实际持有的外键回收。"""

import logging

from sqlalchemy import delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from comfyshop_api.models import (
    Artifact,
    Asset,
    Execution,
    MediaObject,
    OriginalDeletion,
    Work,
    WorkAsset,
    now_ms,
)
from comfyshop_media.storage import MediaStorage
from comfyshop_media.uploads import ReceivedMedia

DELETE_RETRY_MS = 60_000
# 候选文件有暂存目录所有者，只有写入结束或所有者退出后才进入普通回收。
UPLOAD_PENDING = -1
_log = logging.getLogger("comfyshop")


class OriginalRequired(Exception):
    """原件尚未登记，先在事务外把文件写入存储。"""


def attach_original(db: Session, upload: ReceivedMedia, stored: bool) -> MediaObject:
    """取共享原件，由调用方在同一事务里写入素材或成品。"""
    if not stored:
        original = db.scalar(
            select(MediaObject)
            .where(MediaObject.sha256 == upload.sha256)
            .with_for_update(read=True, key_share=True)
        )
        if original is None:
            raise OriginalRequired
        return original

    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(MediaObject).values(
        sha256=upload.sha256,
        storage_name=upload.path.name,
        size=upload.size,
        content_type=upload.content_type,
        width=upload.width,
        height=upload.height,
        duration_ms=upload.duration_ms,
    )
    # 并发上传复用先登记的原件。冲突分支取得行锁并返回当前原件。
    original = db.scalars(
        statement.on_conflict_do_update(
            index_elements=[MediaObject.sha256], set_={"sha256": statement.excluded.sha256}
        ).returning(MediaObject)
    ).one()
    if original.storage_name == upload.path.name:
        db.execute(
            delete(OriginalDeletion).where(OriginalDeletion.storage_name == upload.path.name)
        )
    return original


def release_uploads(db: Session, names: list[str]) -> None:
    """重新排队已结束或中断的候选写入。登记成功的原件在提交时已经移出队列。"""
    if names:
        db.execute(
            update(OriginalDeletion)
            .where(
                OriginalDeletion.storage_name.in_(names),
                OriginalDeletion.retry_at == UPLOAD_PENDING,
            )
            .values(retry_at=0)
        )
        db.commit()


def retire_unreferenced_originals(db: Session) -> None:
    """登记没有素材、成品、封面或作品输入引用的原件。"""
    unreferenced = (
        ~exists().where(Asset.sha256 == MediaObject.sha256)
        & ~exists().where(Artifact.sha256 == MediaObject.sha256)
        & ~exists().where(Execution.cover_image_sha256 == MediaObject.sha256)
        & ~exists().where(Work.cover_image_sha256 == MediaObject.sha256)
        & ~exists().where(WorkAsset.sha256 == MediaObject.sha256)
    )
    candidates = list(
        db.scalars(
            select(MediaObject.sha256)
            .where(unreferenced)
            .order_by(MediaObject.sha256)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    )
    if candidates:
        # 取得原件行锁后用新语句核对外键，涵盖选择期间刚提交的引用。
        names = db.scalars(
            delete(MediaObject)
            .where(MediaObject.sha256.in_(candidates), unreferenced)
            .returning(MediaObject.storage_name)
        )
        db.add_all(OriginalDeletion(storage_name=name, retry_at=0) for name in names)
    db.commit()


def delete_pending_originals(db: Session, storage: MediaStorage) -> None:
    """回收已退役的文件和未被选中的候选文件，释放数据库连接后访问存储。"""
    names = list(
        db.scalars(
            select(OriginalDeletion.storage_name)
            .where(OriginalDeletion.retry_at.between(0, now_ms()))
            .order_by(OriginalDeletion.retry_at, OriginalDeletion.storage_name)
            .limit(100)
        )
    )
    registered = (
        set(db.scalars(select(MediaObject.storage_name).where(MediaObject.storage_name.in_(names))))
        if names
        else set()
    )
    db.rollback()
    removed = []
    for name in names:
        try:
            if name not in registered:
                storage.delete(name)
        except (OSError, ValueError):
            _log.exception("媒体原文件清理失败")
            # 存储故障时缩短本轮工作，下一轮仍可处理剩余文件。
            db.execute(
                update(OriginalDeletion)
                .where(OriginalDeletion.storage_name == name)
                .values(retry_at=now_ms() + DELETE_RETRY_MS)
            )
            break
        removed.append(name)
    if removed:
        db.execute(delete(OriginalDeletion).where(OriginalDeletion.storage_name.in_(removed)))
    db.commit()
