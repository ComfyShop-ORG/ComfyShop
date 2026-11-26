"""提供可见的作者资料及其头像。"""

from uuid import UUID

from fastapi import APIRouter, Request, Response

from comfyshop_api.schemas import AuthorRead
from comfyshop_api.security import DB, MaybeSession
from comfyshop_api.services import avatars, profiles

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("/{username}")
def get_author(username: str, db: DB, session: MaybeSession) -> AuthorRead:
    return AuthorRead.from_user(
        profiles.read_author(db, username, session.user_id if session else None)
    )


@router.get(
    "/{user_id}/avatar/{version}",
    response_class=Response,
    responses=avatars.RESPONSES,
)
def get_avatar(
    user_id: UUID,
    request: Request,
    db: DB,
    session: MaybeSession,
    version: avatars.AvatarVersion,
) -> Response:
    image = profiles.read_avatar(db, str(user_id), version, session.user_id if session else None)
    return avatars.avatar_response(request, version, image)
