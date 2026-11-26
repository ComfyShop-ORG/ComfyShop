"""读写个人资料及经过验证的头像。"""

from fastapi import HTTPException
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session, aliased

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Team, TeamMember, User, Work, Workflow
from comfyshop_api.security import lock_session_account
from comfyshop_api.services.accounts import DELETED_NAME
from comfyshop_api.services.avatars import set_avatar
from comfyshop_api.services.public_catalog import public_work_condition
from comfyshop_api.services.workspace_shares import workspace_shared_to


def update_nickname(db: Session, user: User, session_hash: str, nickname: str | None) -> None:
    if nickname == DELETED_NAME:
        raise HTTPException(422, msg("profile.thisDisplayNameIsUnavailable"))
    lock_session_account(db, user, session_hash)
    user.nickname = nickname


def update_avatar(db: Session, user: User, session_hash: str, image: bytes | None) -> None:
    lock_session_account(db, user, session_hash)
    set_avatar(user, image)


def _visible_profile(viewer_id: str | None) -> ColumnElement[bool]:
    public_workflow = (
        select(Workflow.id)
        .where(Workflow.owner_id == User.id, Workflow.publicly_visible())
        .exists()
    )
    public_work = (
        select(Work.id)
        .join(Workflow)
        .where(Work.owner_id == User.id, public_work_condition())
        .exists()
    )
    return User.deleted_at.is_(None) & or_(
        User.id == viewer_id, public_workflow, public_work, workspace_shared_to(User.id, viewer_id)
    )


def read_author(db: Session, username: str, viewer_id: str | None) -> User:
    user = db.scalar(
        select(User).where(User.username_key == username.casefold(), _visible_profile(viewer_id))
    )
    if user is None:
        raise HTTPException(404, msg("profile.authorProfileUnavailable"))
    return user


def read_avatar(db: Session, user_id: str, version: str, viewer_id: str | None) -> bytes:
    visible = _visible_profile(viewer_id)
    if viewer_id is not None:
        viewer = aliased(TeamMember)
        teammate = (
            select(Team.id)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .join(viewer, viewer.team_id == Team.id)
            .where(
                Team.archived_at.is_(None),
                TeamMember.user_id == User.id,
                viewer.user_id == viewer_id,
            )
            .exists()
        )
        visible |= User.deleted_at.is_(None) & teammate
    image = db.scalar(
        select(User.avatar_image).where(User.id == user_id, User.avatar_digest == version, visible)
    )
    if image is None:
        raise HTTPException(404, msg("profile.avatarNotFound"))
    return image
