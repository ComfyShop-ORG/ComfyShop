"""提供可见的作者资料及其头像。"""

from uuid import UUID

from fastapi import APIRouter, Path, Request, Response

from comfyshop_api.schemas import AuthorRead
from comfyshop_api.security import DB, MaybeSession
from comfyshop_api.services import profiles
from comfyshop_api.services.media_responses import image_revalidation

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("/{username}", response_model=AuthorRead)
def get_author(username: str, db: DB, session: MaybeSession) -> AuthorRead:
    return AuthorRead.from_user(
        profiles.read_author(db, username, session.user_id if session else None)
    )


@router.get(
    "/{user_id}/avatar/{version}",
    response_class=Response,
    responses={
        200: {"content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}}},
        304: {"description": "头像未修改"},
    },
)
def get_avatar(
    user_id: UUID,
    request: Request,
    db: DB,
    session: MaybeSession,
    version: str = Path(pattern=r"^[a-f0-9]{64}$"),
) -> Response:
    image = profiles.read_avatar(db, str(user_id), version, session.user_id if session else None)
    headers, unchanged = image_revalidation(request, version)
    if unchanged:
        return Response(status_code=304, headers=headers)
    return Response(image, media_type="image/webp", headers=headers)
