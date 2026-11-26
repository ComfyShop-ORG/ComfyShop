"""个人和团队头像共用的上传、转码和缓存规则。"""

from hashlib import sha256
from typing import Annotated

from anyio import CapacityLimiter, to_thread
from fastapi import HTTPException, Path, Request, Response

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Team, User
from comfyshop_api.services.media_responses import image_revalidation
from comfyshop_media.renditions import avatar_thumbnail

AvatarVersion = Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]
UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}
RESPONSES: dict[int | str, dict[str, object]] = {
    200: {"content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}}},
    304: {"description": "头像未修改"},
}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_avatar_threads = CapacityLimiter(2)


async def receive_avatar(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length and (not length.isdecimal() or int(length) > _MAX_AVATAR_BYTES):
        raise HTTPException(413, msg("profile.theAvatarCannotExceedMb"))
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > _MAX_AVATAR_BYTES:
            raise HTTPException(413, msg("profile.theAvatarCannotExceedMb"))
        content.extend(chunk)
    return await to_thread.run_sync(avatar_thumbnail, bytes(content), limiter=_avatar_threads)


def set_avatar(profile: User | Team, image: bytes | None) -> bool:
    version = sha256(image).hexdigest() if image is not None else None
    if version == profile.avatar_digest:
        return False
    profile.avatar_image = image
    profile.avatar_digest = version
    return True


def avatar_response(request: Request, version: str, image: bytes) -> Response:
    headers, unchanged = image_revalidation(request, version)
    if unchanged:
        return Response(status_code=304, headers=headers)
    return Response(image, media_type="image/webp", headers=headers)
