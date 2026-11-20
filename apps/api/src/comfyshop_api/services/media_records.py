"""将素材与成品的业务记录转换成经过平台授权的媒体地址。"""

from typing import Literal

from sqlalchemy.orm import Session

from comfyshop_api.models import Artifact, Asset, MediaObject, Task
from comfyshop_api.schemas import ArtifactRead, AssetRead, MediaRead, ThumbnailRead
from comfyshop_media.renditions import MAX_VIDEO_PREVIEW_SIZE, MediaSource, thumbnail_sizes


def media_source(media: MediaObject) -> MediaSource:
    return MediaSource(
        media.storage_name, media.sha256, media.content_type, media.width, media.height
    )


def detach_media_record(db: Session, record: Asset | Artifact) -> None:
    """在读媒体字节前结束事务，保留已经读取的业务记录和媒体元数据。"""
    db.expunge(record.media)
    db.expunge(record)
    db.rollback()


def artifact_media(artifact: Artifact, frame_ms: int | None = None) -> MediaRead:
    """视频指定的封面画面引用独立的缩略图路径。"""
    return _media_read("artifacts", artifact, frame_ms)


def _media_read(
    kind: Literal["assets", "artifacts"], record: Asset | Artifact, frame_ms: int | None = None
) -> MediaRead:
    media = record.media
    base = f"/api/v1/{kind}/{record.id}"
    original = f"{base}/file"
    video = media.content_type.startswith("video/")
    thumbnail = f"{base}/frames/{frame_ms}/thumbnail" if video and frame_ms else f"{base}/thumbnail"
    return MediaRead(
        src=thumbnail if video else original,
        video=original if video else None,
        width=media.width,
        height=media.height,
        thumbnail=ThumbnailRead(src=thumbnail, sizes=thumbnail_sizes(media.width, media.height)),
        video_preview=ThumbnailRead(
            src=f"{base}/video-preview",
            sizes=thumbnail_sizes(media.width, media.height, maximum=MAX_VIDEO_PREVIEW_SIZE),
        )
        if video and kind == "artifacts"
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
        content_type=artifact.media.content_type,
        media=artifact_media(artifact),
        execution_id=artifact.execution_id,
        output_node_id=artifact.output_node_id,
        output_node_title=artifact.output_node_title,
        output_slot=artifact.output_slot,
        output_index=artifact.output_index,
        created=artifact.created_at,
    )


def asset_read(asset: Asset) -> AssetRead:
    return AssetRead(
        id=asset.id,
        filename=asset.filename,
        sha256=asset.sha256,
        size=asset.media.size,
        content_type=asset.media.content_type,
        media=_media_read("assets", asset),
    )
