"""将素材与成品的业务记录转换成经过平台授权的媒体地址。"""

from collections.abc import Sequence
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Artifact, Asset, MediaObject, MediaRecord, Task, WorkAsset
from comfyshop_api.schemas import (
    ArtifactRead,
    AssetRead,
    CoverImageRead,
    MediaKind,
    MediaRead,
    ThumbnailRead,
)
from comfyshop_media.model_exports import MODEL_CONTENT_TYPES
from comfyshop_media.renditions import MAX_VIDEO_PREVIEW_SIZE, MediaSource, thumbnail_sizes
from comfyshop_media.uploads import TEXT_EXPORT_CONTENT_TYPES


def media_source(media: MediaObject | MediaRecord) -> MediaSource:
    original = media.media if isinstance(media, MediaRecord) else media
    if (
        media_kind(media.content_type) not in {"image", "video"}
        or original.width is None
        or original.height is None
    ):
        raise HTTPException(404, msg("media.thisOutputHasNoImagePreview"))
    return MediaSource(
        original.storage_name, original.sha256, media.content_type, original.width, original.height
    )


def media_kind(content_type: str) -> MediaKind:
    if content_type in MODEL_CONTENT_TYPES:
        return "3d"
    if content_type in TEXT_EXPORT_CONTENT_TYPES.values():
        return "text"
    if content_type.startswith("audio/"):
        return "audio"
    return "video" if content_type.startswith("video/") else "image"


def detach_media_record(db: Session, record: MediaRecord) -> None:
    """在读媒体字节前结束事务，保留已经读取的业务记录和媒体元数据。"""
    db.expunge(record.media)
    db.expunge(record)
    db.rollback()


def artifact_media(artifact: Artifact, frame_ms: int | None = None) -> MediaRead:
    """视频指定的封面画面引用独立的缩略图路径。"""
    return _media_read(f"/api/v1/artifacts/{artifact.id}", artifact, frame_ms)


def preferred_cover(artifacts: Sequence[Artifact]) -> Artifact:
    """在按输出顺序排列的成品中优先选图片、视频，然后取第一份原件。"""
    return min(
        artifacts,
        key=lambda item: {"image": 0, "video": 1}.get(media_kind(item.content_type), 2),
    )


def cover_image_read(
    resource: Literal["executions", "works", "workflows"],
    record_id: str,
    media: MediaObject | None,
) -> CoverImageRead | None:
    if media is None:
        return None
    source = media_source(media)
    src = f"/api/v1/{resource}/{record_id}/cover/{source.sha256}/thumbnail"
    return CoverImageRead(
        sha256=source.sha256,
        src=src,
        width=source.width,
        height=source.height,
        thumbnail=ThumbnailRead(src=src, sizes=thumbnail_sizes(source.width, source.height)),
    )


def _media_read(base: str, record: MediaRecord, frame_ms: int | None = None) -> MediaRead:
    media = record.media
    original = f"{base}/file"
    media_type = media_kind(record.content_type)
    if media_type in {"audio", "3d", "text"}:
        return MediaRead(
            src=original,
            width=None,
            height=None,
            kind=media_type,
            filename=record.filename,
            duration_ms=media.duration_ms,
        )
    width, height = media.width, media.height
    assert width is not None and height is not None
    video = media_type == "video"
    thumbnail = f"{base}/frames/{frame_ms}/thumbnail" if video and frame_ms else f"{base}/thumbnail"
    return MediaRead(
        src=thumbnail if video else original,
        video=original if video else None,
        width=width,
        height=height,
        kind=media_type,
        duration_ms=media.duration_ms,
        thumbnail=ThumbnailRead(src=thumbnail, sizes=thumbnail_sizes(width, height)),
        video_preview=ThumbnailRead(
            src=f"{base}/video-preview",
            sizes=thumbnail_sizes(width, height, maximum=MAX_VIDEO_PREVIEW_SIZE),
        )
        if video and isinstance(record, Artifact)
        else None,
    )


def artifact_read(artifact: Artifact, task: Task) -> ArtifactRead:
    return ArtifactRead(
        id=artifact.id,
        task_id=task.id,
        workflow_id=task.workflow_id,
        workflow_name=task.workflow_name,
        filename=artifact.filename,
        sha256=artifact.sha256,
        size=artifact.media.size,
        content_type=artifact.content_type,
        media=artifact_media(artifact),
        execution_id=artifact.execution_id,
        output_node_id=artifact.output_node_id,
        output_node_title=artifact.output_node_title,
        output_slot=artifact.output_slot,
        output_index=artifact.output_index,
        created=artifact.created_at,
    )


def asset_read(asset: Asset | WorkAsset) -> AssetRead:
    base = (
        f"/api/v1/works/{asset.work_id}/assets/{asset.id}"
        if isinstance(asset, WorkAsset)
        else f"/api/v1/assets/{asset.id}"
    )
    return AssetRead(
        id=asset.id,
        filename=asset.filename,
        sha256=asset.sha256,
        size=asset.media.size,
        content_type=asset.content_type,
        media=_media_read(base, asset),
        saved_at=asset.saved_at if isinstance(asset, Asset) else None,
    )
