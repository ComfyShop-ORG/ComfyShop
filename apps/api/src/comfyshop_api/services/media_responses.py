"""在路由完成读取授权后，将媒体文件和派生内容转为 HTTP 响应。"""

from contextlib import closing
from email.utils import formatdate
from pathlib import Path

from anyio import CapacityLimiter, to_thread
from fastapi import Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.types import Receive, Scope, Send

from comfyshop_api.models import MediaObject
from comfyshop_api.services.media_records import media_source
from comfyshop_media.errors import MediaError
from comfyshop_media.renditions import read_thumbnail, thumbnail_key, video_preview
from comfyshop_media.settings import MediaSettings
from comfyshop_media.staging import StagingDirectory
from comfyshop_media.storage import MediaStorage, ObjectRead

THUMBNAIL_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "content": {
            "image/webp": {"schema": {"type": "string", "format": "binary"}},
            "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
        }
    }
}

# 独立于工作机心跳和回传等接口的线程池限额。
_thumbnail_threads = CapacityLimiter(4)
_preview_threads = CapacityLimiter(2)


class _ObjectResponse(StreamingResponse):
    def __init__(self, original: ObjectRead, headers: dict[str, str]) -> None:
        self.body_stream = original.body
        headers.update(
            {
                "content-length": str(original.size),
                "etag": original.etag,
                "last-modified": formatdate(original.last_modified.timestamp(), usegmt=True),
            }
        )
        if original.content_range:
            headers["content-range"] = original.content_range
        super().__init__(
            original.body.iter_chunks(chunk_size=128 * 1024),
            206 if original.content_range else 200,
            headers,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        with closing(self.body_stream):
            await super().__call__(scope, receive, send)


def original_response(
    request: Request,
    storage: MediaStorage,
    media: MediaObject,
    filename: str,
    download: bool = False,
) -> Response:
    path = storage.original_path(media.storage_name)
    response = FileResponse(
        path or media.storage_name,
        media_type=media.content_type,
        filename=filename,
        content_disposition_type="attachment" if download else "inline",
    )
    if path is not None:
        return response

    byte_range = request.headers.get("range")
    # S3 一次支持一个区间，多段请求回退到完整响应。
    if byte_range and "," in byte_range:
        byte_range = None
    if byte_range and (if_range := request.headers.get("if-range")):
        etag, modified = storage.original_validators(media.storage_name)
        if if_range not in {etag, formatdate(modified.timestamp(), usegmt=True)}:
            byte_range = None
    try:
        original = storage.open_original(media.storage_name, byte_range)
    except MediaError as error:
        if error.kind == "range":
            return Response(status_code=416, headers={"Content-Range": f"bytes */{media.size}"})
        if error.kind == "range_syntax" and byte_range:
            return Response(str(error), status_code=400, media_type="text/plain")
        raise
    return _ObjectResponse(original, dict(response.headers))


async def thumbnail_response(
    request: Request, media: MediaObject, config: MediaSettings, size: int | None, frame_ms: int = 0
) -> Response:
    source = media_source(media)
    tag = f'"{thumbnail_key(source, size, frame_ms)}"'
    headers = {"Cache-Control": "private, no-cache", "ETag": tag}
    condition = request.headers.get("if-none-match", "")
    tags = {value.strip().removeprefix("W/") for value in condition.split(",")}
    if "*" in tags or tag in tags:
        return Response(status_code=304, headers=headers)
    content, content_type = await to_thread.run_sync(
        read_thumbnail, source, config, size, frame_ms, limiter=_thumbnail_threads
    )
    return Response(content, media_type=content_type, headers=headers)


class _PreviewResponse(FileResponse):
    def __init__(self, path: Path, directory: StagingDirectory) -> None:
        self.directory = directory
        super().__init__(path, media_type="video/mp4")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self.directory.aclose()


async def video_preview_response(media: MediaObject, config: MediaSettings, size: int) -> Response:
    directory = await to_thread.run_sync(config.media_storage.staging_directory)
    try:
        path = await to_thread.run_sync(
            video_preview,
            media_source(media),
            config,
            size,
            Path(directory.name) / "preview.mp4",
            limiter=_preview_threads,
        )
        return _PreviewResponse(path, directory)
    except BaseException:
        await directory.aclose()
        raise
