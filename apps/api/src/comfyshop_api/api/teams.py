from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from comfyshop_api.core.i18n import msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import TeamRole, User
from comfyshop_api.schemas import (
    ArchivedTeamPage,
    ErrorRead,
    PublicTeamRead,
    TeamEventCategory,
    TeamEventPage,
    TeamMemberChange,
    TeamMemberPage,
    TeamName,
    TeamPage,
    TeamProfileVisibility,
    TeamRead,
)
from comfyshop_api.security import (
    DB,
    CurrentUser,
    LockedWriter,
    MaybeSession,
    Writer,
    lock_writer,
    require_account_by_username,
)
from comfyshop_api.services import avatars, public_teams, team_events, teams
from comfyshop_api.services.teams import TeamAccess, require_team

router = APIRouter(prefix="/teams", tags=["teams"])


def team_reader(
    db: DB, request: Request, session: MaybeSession, workspace_team: UUID | None = None
) -> TeamAccess | None:
    if workspace_team is None:
        return None
    if "workspace_owner" in request.query_params:
        raise HTTPException(422, msg("team.chooseOneWorkspace"))
    if session is None:
        raise HTTPException(401, msg("workflow.signInToContinue"))
    return require_team(db, str(workspace_team), session.user_id)


TeamReader = Annotated[TeamAccess | None, Depends(team_reader)]


def scoped_team_writer(
    db: DB, user: User, team: TeamAccess | None, minimum: TeamRole
) -> TeamAccess | None:
    return require_team(db, team.team.id, user.id, minimum=minimum, locked=True) if team else None


def scoped_team_editor(db: DB, user: LockedWriter, team: TeamReader) -> TeamAccess | None:
    return scoped_team_writer(db, user, team, TeamRole.EDITOR)


def scoped_team_manager(db: DB, user: LockedWriter, team: TeamReader) -> TeamAccess | None:
    return scoped_team_writer(db, user, team, TeamRole.MANAGER)


TeamEditor = Annotated[TeamAccess | None, Depends(scoped_team_editor)]
TeamManager = Annotated[TeamAccess | None, Depends(scoped_team_manager)]


def team_editor(team_id: UUID, db: DB, user: User) -> TeamAccess:
    return require_team(db, str(team_id), user.id, minimum=TeamRole.EDITOR, locked=True)


def team_manager(team_id: UUID, db: DB, user: User) -> TeamAccess:
    return require_team(db, str(team_id), user.id, minimum=TeamRole.MANAGER, locked=True)


def lock_membership_change(
    request: Request, db: DB, user: User, team_id: str, member_id: str, minimum: TeamRole
) -> TeamAccess:
    # 先按账号 ID 依序取锁，防止退出、注销、邀请或转让并发时保留失效的成员关系。
    for account_id in sorted({user.id, member_id}):
        if account_id == user.id:
            lock_writer(request, db, user)
        else:
            write_lock(db, User, account_id)
    return require_team(db, team_id, user.id, minimum=minimum, locked=True)


Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=100)]
EventTime = Annotated[int | None, Query(ge=-8_640_000_000_000_000, le=8_640_000_000_000_000)]


@router.get("")
def list_teams(db: DB, user: CurrentUser, cursor: Cursor = None, limit: Limit = 24) -> TeamPage:
    return teams.list_teams(db, user.id, cursor, limit)


@router.post("", status_code=201)
def create_team(body: TeamName, db: DB, user: LockedWriter) -> TeamRead:
    return teams.create_team(db, user.id, body.name)


@router.get("/archived")
def list_archived_teams(
    db: DB, user: CurrentUser, cursor: Cursor = None, limit: Limit = 24
) -> ArchivedTeamPage:
    return teams.list_archived_teams(db, user.id, cursor, limit)


@router.get("/{team_id}")
def get_team(team_id: UUID, db: DB, user: CurrentUser) -> TeamRead:
    return require_team(db, str(team_id), user.id).read()


@router.get("/{team_id}/public")
def get_public_team(team_id: UUID, db: DB) -> PublicTeamRead:
    return public_teams.read_public_team(db, str(team_id))


@router.put("/{team_id}/profile-visibility")
def set_team_profile_visibility(
    team_id: UUID, body: TeamProfileVisibility, db: DB, user: LockedWriter
) -> TeamRead:
    return teams.update_profile_visibility(db, team_manager(team_id, db, user), body.public)


@router.patch("/{team_id}")
def rename_team(team_id: UUID, body: TeamName, db: DB, user: LockedWriter) -> TeamRead:
    return teams.rename_team(db, team_manager(team_id, db, user), body.name)


@router.put("/{team_id}/avatar", openapi_extra=avatars.UPLOAD_BODY)
async def upload_team_avatar(team_id: UUID, request: Request, db: DB, user: Writer) -> TeamRead:
    await run_in_threadpool(require_team, db, str(team_id), user.id, minimum=TeamRole.MANAGER)
    image = await avatars.receive_avatar(request)

    def save() -> TeamRead:
        access = team_manager(team_id, db, lock_writer(request, db, user))
        return teams.update_avatar(db, access, image)

    return await run_in_threadpool(save)


@router.delete("/{team_id}/avatar")
def remove_team_avatar(team_id: UUID, db: DB, user: LockedWriter) -> TeamRead:
    return teams.update_avatar(db, team_manager(team_id, db, user), None)


@router.get("/{team_id}/avatar/{version}", response_class=Response, responses=avatars.RESPONSES)
def get_team_avatar(
    team_id: UUID, version: avatars.AvatarVersion, request: Request, db: DB, session: MaybeSession
) -> Response:
    image = teams.read_avatar(db, str(team_id), version, session.user_id if session else None)
    return avatars.avatar_response(request, version, image)


@router.get("/{team_id}/members")
def list_members(
    team_id: UUID, db: DB, user: CurrentUser, cursor: Cursor = None, limit: Limit = 24
) -> TeamMemberPage:
    return teams.list_members(db, require_team(db, str(team_id), user.id).team.id, cursor, limit)


@router.get("/{team_id}/events")
def list_events(
    team_id: UUID,
    db: DB,
    user: CurrentUser,
    actor: Annotated[str | None, Query(max_length=64)] = None,
    category: TeamEventCategory | None = None,
    created_from: EventTime = None,
    created_before: EventTime = None,
    cursor: Cursor = None,
    limit: Limit = 24,
) -> TeamEventPage:
    access = require_team(db, str(team_id), user.id, minimum=TeamRole.MANAGER)
    return team_events.list_events(
        db,
        access,
        actor=actor,
        category=category,
        created_from=created_from,
        created_before=created_before,
        cursor=cursor,
        limit=limit,
    )


@router.put("/{team_id}/members/by-name/{username}", status_code=204)
def set_member(
    team_id: UUID,
    username: Annotated[str, Path(min_length=2, max_length=32)],
    body: TeamMemberChange,
    request: Request,
    db: DB,
    user: Writer,
) -> None:
    require_team(db, str(team_id), user.id, minimum=TeamRole.MANAGER)
    account = require_account_by_username(db, username)
    access = lock_membership_change(request, db, user, str(team_id), account.id, TeamRole.MANAGER)
    teams.set_member(db, access, account, body.role)


@router.delete("/{team_id}/members/{member_id}", status_code=204)
def remove_member(team_id: UUID, member_id: UUID, request: Request, db: DB, user: Writer) -> None:
    target = str(member_id)
    minimum = TeamRole.READER if target == user.id else TeamRole.MANAGER
    require_team(db, str(team_id), user.id, minimum=minimum)
    access = lock_membership_change(request, db, user, str(team_id), target, minimum)
    teams.remove_member(db, access, target)


@router.put("/{team_id}/owner/{member_id}")
def transfer_team(
    team_id: UUID, member_id: UUID, request: Request, db: DB, user: Writer
) -> TeamRead:
    require_team(db, str(team_id), user.id, minimum=TeamRole.OWNER)
    access = lock_membership_change(request, db, user, str(team_id), str(member_id), TeamRole.OWNER)
    return teams.transfer_team(db, access, str(member_id))


@router.delete("/{team_id}", status_code=204, responses={409: {"model": ErrorRead}})
def archive_team(team_id: UUID, db: DB, user: LockedWriter) -> None:
    teams.archive_team(
        db, require_team(db, str(team_id), user.id, minimum=TeamRole.OWNER, locked=True)
    )


@router.post("/{team_id}/restore")
def restore_team(team_id: UUID, db: DB, user: LockedWriter) -> TeamRead:
    return teams.restore_team(db, str(team_id), user.id)
