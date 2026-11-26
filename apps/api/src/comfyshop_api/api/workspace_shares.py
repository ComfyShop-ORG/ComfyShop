from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import delete

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import WorkspaceShare
from comfyshop_api.schemas import WorkspaceShareAccount, WorkspaceSharePage
from comfyshop_api.security import DB, CurrentUser, LockedWriter, MaybeSession
from comfyshop_api.services.workspace_shares import (
    grant_workspace_share,
    list_workspace_shares,
    shared_workspace,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


def require_shared_workspace(db: DB, owner_id: UUID, viewer_id: str) -> WorkspaceShareAccount:
    owner = shared_workspace(db, str(owner_id), viewer_id)
    if owner is None:
        raise HTTPException(404, msg("workspaceShare.unavailable"))
    return owner


def workspace_reader(
    db: DB, session: MaybeSession, workspace_owner: UUID | None = None
) -> str | None:
    """只用于读取，返回当前登录账号或已经授权的空间所有者 ID。"""
    if workspace_owner is None:
        return session.user_id if session else None
    if session is None:
        raise HTTPException(401, msg("workflow.signInToContinue"))
    return require_shared_workspace(db, workspace_owner, session.user_id).id


WorkspaceReader = Annotated[str | None, Depends(workspace_reader)]


def signed_in_workspace_reader(owner_id: WorkspaceReader) -> str:
    if owner_id is None:
        raise HTTPException(401, msg("workflow.signInToContinue"))
    return owner_id


SignedInWorkspaceReader = Annotated[str, Depends(signed_in_workspace_reader)]


@router.get("/shares")
def workspace_shares(
    db: DB,
    user: CurrentUser,
    direction: Literal["sent", "received"],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> WorkspaceSharePage:
    return list_workspace_shares(db, user.id, direction, cursor, limit)


@router.put("/shares/by-name/{username}", status_code=204)
def add_workspace_share(
    username: Annotated[str, Path(min_length=2, max_length=32)], db: DB, user: LockedWriter
) -> None:
    grant_workspace_share(db, user.id, username)


@router.delete("/shares/{viewer_id}", status_code=204)
def revoke_workspace_share(viewer_id: UUID, db: DB, user: LockedWriter) -> None:
    db.execute(
        delete(WorkspaceShare).where(
            WorkspaceShare.owner_id == user.id, WorkspaceShare.viewer_id == str(viewer_id)
        )
    )
    db.commit()


@router.get("/shared/{owner_id}")
def shared_workspace_account(owner_id: UUID, db: DB, user: CurrentUser) -> WorkspaceShareAccount:
    return require_shared_workspace(db, owner_id, user.id)
