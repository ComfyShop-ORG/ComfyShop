"""读写个人资料及经过验证的头像。"""

from hashlib import sha256

from anyio import CapacityLimiter, to_thread
from fastapi import HTTPException, Request
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from comfyshop_api.models import User, Work, Workflow
from comfyshop_api.security import lock_session_account
from comfyshop_api.services.accounts import DELETED_NAME
from comfyshop_api.services.works import public_work_condition
from comfyshop_media.renditions import avatar_thumbnail

_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_avatar_threads = CapacityLimiter(2)


async def receive_avatar(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length and (not length.isdecimal() or int(length) > _MAX_AVATAR_BYTES):
        raise HTTPException(413, "头像不能超过 5 MB")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > _MAX_AVATAR_BYTES:
            raise HTTPException(413, "头像不能超过 5 MB")
        content.extend(chunk)
    return await to_thread.run_sync(avatar_thumbnail, bytes(content), limiter=_avatar_threads)


def update_nickname(db: Session, user: User, session_hash: str, nickname: str | None) -> None:
    if nickname == DELETED_NAME:
        raise HTTPException(422, "这个昵称不可用")
    lock_session_account(db, user, session_hash)
    user.nickname = nickname


def update_avatar(db: Session, user: User, session_hash: str, image: bytes | None) -> None:
    version = sha256(image).hexdigest() if image is not None else None
    lock_session_account(db, user, session_hash)
    if version != user.avatar_digest:
        user.avatar_image = image
        user.avatar_digest = version


def _visible_profile(viewer_id: str | None) -> ColumnElement[bool]:
    public_workflow = (
        select(Workflow.id)
        .where(Workflow.owner_id == User.id, Workflow.visible(), Workflow.published.is_(True))
        .exists()
    )
    public_work = (
        select(Work.id)
        .join(Workflow)
        .where(Work.owner_id == User.id, public_work_condition())
        .exists()
    )
    return User.deleted_at.is_(None) & or_(User.id == viewer_id, public_workflow, public_work)


def read_author(db: Session, username: str, viewer_id: str | None) -> User:
    user = db.scalar(
        select(User).where(User.username_key == username.casefold(), _visible_profile(viewer_id))
    )
    if user is None:
        raise HTTPException(404, "作者资料不可用")
    return user


def read_avatar(db: Session, user_id: str, version: str, viewer_id: str | None) -> bytes:
    image = db.scalar(
        select(User.avatar_image).where(
            User.id == user_id, User.avatar_digest == version, _visible_profile(viewer_id)
        )
    )
    if image is None:
        raise HTTPException(404, "头像不存在")
    return image
