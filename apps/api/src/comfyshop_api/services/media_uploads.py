"""接收经过授权的 HTTP 上传，并协调原件存储与业务登记。"""

import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.core.i18n import msg
from comfyshop_api.models import OriginalDeletion
from comfyshop_api.services.originals import UPLOAD_PENDING, OriginalRequired, release_uploads
from comfyshop_media.uploads import ReceivedMedia, receive_media


async def upload_media[T](
    request: Request,
    db: Session,
    config: Settings,
    limit: int,
    record: Callable[[ReceivedMedia, bool], tuple[T, bool]],
    expected_hash: str | None = None,
    *,
    export_filename: str | None = None,
    source_filename: str | None = None,
) -> T:
    length = request.headers.get("content-length")
    if length and (not length.isdecimal() or int(length) > limit):
        raise HTTPException(413, msg("media.theFileIsTooLarge"))

    storage = config.media_storage
    staging = await run_in_threadpool(storage.staging_directory)
    try:
        media = await receive_media(
            request.stream(),
            Path(staging.name),
            limit,
            config.ffprobe,
            expected_hash,
            export_filename=export_filename,
            source_filename=source_filename,
        )

        def save() -> T:
            try:
                result, _ = record(media, False)
                return result
            except OriginalRequired:
                pass
            name = media.path.name
            staging.keep_for_recovery = True
            db.add(OriginalDeletion(storage_name=name, retry_at=UPLOAD_PENDING))
            db.commit()
            kept = False
            try:
                storage.put(name, media.path, media.content_type)
                result, kept = record(media, True)
                return result
            finally:
                if kept:
                    staging.keep_for_recovery = False
                else:
                    try:
                        db.rollback()
                        release_uploads(db, [name])
                        staging.keep_for_recovery = False
                    except SQLAlchemyError:
                        # 数据库恢复后由持久卷中的暂存文件定位尚未释放的候选记录。
                        logging.getLogger("comfyshop").exception("候选原件等待后台回收")

        return await run_in_threadpool(save)
    finally:
        await staging.aclose()
