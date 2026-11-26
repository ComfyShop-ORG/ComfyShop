"""个人空间的只读授权，用账号 ID 关联所有者和受邀人。"""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import User, WorkspaceShare
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import WorkspaceShareAccount, WorkspaceSharePage
from comfyshop_api.security import require_account_by_username
from comfyshop_api.services.teams import find_team


def workspace_shared_to(
    owner_id: str | InstrumentedAttribute[str], viewer_id: str | None
) -> ColumnElement[bool]:
    return exists().where(
        WorkspaceShare.owner_id == owner_id, WorkspaceShare.viewer_id == viewer_id
    )


def shared_workspace(db: Session, owner_id: str, viewer_id: str) -> WorkspaceShareAccount | None:
    row = db.execute(
        select(User.id, User.username).where(
            User.id == owner_id, User.deleted_at.is_(None), workspace_shared_to(User.id, viewer_id)
        )
    ).one_or_none()
    return WorkspaceShareAccount(id=row.id, username=row.username) if row else None


def has_workspace_share(db: Session, owner_id: str, viewer_id: str | None) -> bool:
    """媒体地址只携带记录 ID，按媒体所属账号核对访问授权。"""
    return viewer_id is not None and shared_workspace(db, owner_id, viewer_id) is not None


def can_read_workspace_media(
    db: Session, owner_id: str, viewer_id: str | None, team_id: str | None
) -> bool:
    if team_id is not None:
        return find_team(db, team_id, viewer_id) is not None
    return owner_id == viewer_id or has_workspace_share(db, owner_id, viewer_id)


def list_workspace_shares(
    db: Session,
    user_id: str,
    direction: Literal["sent", "received"],
    cursor: str | None,
    limit: int,
) -> WorkspaceSharePage:
    if direction == "sent":
        peer, account = WorkspaceShare.viewer_id, WorkspaceShare.owner_id
    else:
        peer, account = WorkspaceShare.owner_id, WorkspaceShare.viewer_id
    query = (
        select(User.id, User.username)
        .join(WorkspaceShare, peer == User.id)
        .where(account == user_id, User.deleted_at.is_(None))
    )
    if position := decode_cursor(cursor, 1):
        query = query.where(User.id > position[0])
    records = db.execute(query.order_by(User.id).limit(limit + 1)).all()
    items, next_cursor = split_page(records, limit, lambda row: (row.id,))
    return WorkspaceSharePage(
        items=[WorkspaceShareAccount(id=row.id, username=row.username) for row in items],
        next_cursor=next_cursor,
    )


def grant_workspace_share(db: Session, owner_id: str, username: str) -> None:
    viewer_id = require_account_by_username(db, username).id
    if viewer_id == owner_id:
        raise HTTPException(422, msg("workspaceShare.self"))
    if db.get(WorkspaceShare, (owner_id, viewer_id)) is None:
        db.add(WorkspaceShare(owner_id=owner_id, viewer_id=viewer_id))
    db.commit()
