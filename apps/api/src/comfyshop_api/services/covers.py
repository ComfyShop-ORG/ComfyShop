"""设置私有结果的封面，以及校验可用作封面的素材和画面。"""

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from comfyshop_api.core.config import Settings
from comfyshop_api.models import Artifact, Asset, Execution, MediaObject, Status, Task
from comfyshop_api.schemas import CoverUpdate
from comfyshop_api.services.artifacts import lock_execution_media
from comfyshop_api.services.executions import owned_execution
from comfyshop_api.services.media_records import media_kind, media_source
from comfyshop_media.renditions import cover_frame


def cover_from_asset(db: Session, asset_id: str, owner_id: str) -> MediaObject:
    """锁住来源素材直到新引用保存。图片之后由封面自己的引用保留。"""
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset_id, Asset.owner_id == owner_id)
        .with_for_update(of=Asset, read=True)
    )
    if asset is None:
        raise HTTPException(404, "素材不存在")
    if not asset.media.content_type.startswith("image/"):
        raise HTTPException(422, "封面需要使用图片")
    return asset.media


def validate_cover_frame(artifact: Artifact, config: Settings, frame_ms: int | None) -> int | None:
    if not frame_ms:
        return None
    if media_kind(artifact.media.content_type) != "video":
        raise HTTPException(422, "只有视频可以选择封面画面")
    return cover_frame(media_source(artifact.media), config, frame_ms)


def _execution_outputs(execution_id: str) -> Select[tuple[Artifact]]:
    return select(Artifact).where(Artifact.execution_id == execution_id, Artifact.visible())


def update_execution_cover(
    db: Session, execution_id: str, owner_id: str, body: CoverUpdate, config: Settings
) -> tuple[Execution, Task]:
    execution, task = owned_execution(db, execution_id, owner_id)
    outputs = _execution_outputs(execution_id)
    frame_ms = None
    if execution.status != Status.SUCCEEDED:
        raise HTTPException(404, "成品不存在")
    if body.artifact_id is not None:
        chosen = outputs.where(Artifact.id == body.artifact_id)
        artifact = db.scalar(chosen)
        if artifact is None:
            raise HTTPException(404, "成品不存在")
        if media_kind(artifact.media.content_type) not in {"image", "video"}:
            raise HTTPException(422, "请选择图片或视频画面作封面")
        # 截帧在写锁外完成，提交前重新核对成品仍然可见。
        frame_ms = validate_cover_frame(artifact, config, body.frame_ms)
        outputs = chosen
    lock_execution_media(db, execution_id)
    db.refresh(execution)
    if db.scalar(outputs.with_only_columns(Artifact.id).limit(1)) is None:
        raise HTTPException(404, "成品不存在")
    if body.asset_id is not None:
        execution.cover_image = cover_from_asset(db, body.asset_id, owner_id)
    else:
        execution.cover_image = None
        execution.cover_artifact_id = body.artifact_id
        execution.cover_frame_ms = frame_ms
    return execution, task


def checked_cover_image(db: Session, image: MediaObject | None, sha256: str) -> MediaObject:
    if image is None or image.sha256 != sha256:
        raise HTTPException(404, "封面不存在")
    db.expunge(image)
    db.rollback()
    return image


def readable_execution_cover(
    db: Session, execution_id: str, owner_id: str, sha256: str
) -> MediaObject:
    execution, _ = owned_execution(db, execution_id, owner_id)
    if execution.status != Status.SUCCEEDED or not db.scalar(
        select(_execution_outputs(execution_id).exists())
    ):
        raise HTTPException(404, "封面不存在")
    return checked_cover_image(db, execution.cover_image, sha256)
