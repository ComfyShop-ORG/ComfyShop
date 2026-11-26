"""团队成员权限与变更记录。内容归团队，写入使用当前账号的身份。"""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session, load_only

from comfyshop_api.core.i18n import msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import Status, Task, Team, TeamEvent, TeamMember, TeamRole, User, now_ms
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ArchivedTeamPage,
    ArchivedTeamRead,
    AuthorRead,
    TeamMemberPage,
    TeamMemberRead,
    TeamPage,
    TeamRead,
)
from comfyshop_api.services.avatars import set_avatar
from comfyshop_api.services.public_teams import public_profile_visible


@dataclass(frozen=True)
class TeamAccess:
    team: Team
    actor_id: str
    role: TeamRole

    def read(self) -> TeamRead:
        return TeamRead.from_team(self.team, self.role)

    def record(self, db: Session, action: str, record_id: str) -> None:
        db.add(
            TeamEvent(
                team_id=self.team.id, actor_id=self.actor_id, action=action, record_id=record_id
            )
        )


def _memberships(actor_id: str) -> Select[tuple[Team, TeamRole]]:
    return (
        select(Team, TeamMember.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == actor_id)
    )


def _active_memberships(actor_id: str) -> Select[tuple[Team, TeamRole]]:
    return _memberships(actor_id).where(Team.archived_at.is_(None))


def find_team(db: Session, team_id: str, actor_id: str | None) -> TeamAccess | None:
    if actor_id is None:
        return None
    row = db.execute(
        _active_memberships(actor_id)
        .where(Team.id == team_id)
        .execution_options(populate_existing=True)
    ).one_or_none()
    return TeamAccess(row[0], actor_id, row.role) if row else None


def require_team(
    db: Session,
    team_id: str,
    actor_id: str,
    *,
    minimum: TeamRole = TeamRole.READER,
    locked: bool = False,
) -> TeamAccess:
    if locked:
        write_lock(db, Team, team_id)
    access = find_team(db, team_id, actor_id)
    if access is None:
        raise HTTPException(404, msg("team.unavailable"))
    if not access.role.permits(minimum):
        raise HTTPException(403, msg("team.permissionDenied"))
    return access


def list_teams(db: Session, actor_id: str, cursor: str | None, limit: int) -> TeamPage:
    query = _active_memberships(actor_id)
    if position := decode_cursor(cursor, 1):
        query = query.where(Team.id > position[0])
    rows = db.execute(query.order_by(Team.id).limit(limit + 1)).all()
    items, next_cursor = split_page(rows, limit, lambda row: (row[0].id,))
    return TeamPage(
        items=[TeamRead.from_team(team, role) for team, role in items],
        next_cursor=next_cursor,
    )


def list_archived_teams(
    db: Session, actor_id: str, cursor: str | None, limit: int
) -> ArchivedTeamPage:
    queued = (
        select(Task.id)
        .where(Task.team_id == Team.id, Task.visible(), Task.status == Status.QUEUED)
        .exists()
    )
    query = (
        _memberships(actor_id)
        .where(TeamMember.role == TeamRole.OWNER, Team.archived_at.is_not(None))
        .with_only_columns(Team.id, Team.name, Team.archived_at, queued.label("has_queued_tasks"))
    )
    if position := decode_cursor(cursor, 2):
        query = query.where(tuple_(Team.archived_at, Team.id) < tuple(position))
    rows = db.execute(
        query.order_by(Team.archived_at.desc(), Team.id.desc()).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(rows, limit, lambda row: (row.archived_at, row.id))
    return ArchivedTeamPage(
        items=[
            ArchivedTeamRead(
                id=row.id,
                name=row.name,
                archived_at=row.archived_at,
                has_queued_tasks=row.has_queued_tasks,
            )
            for row in items
        ],
        next_cursor=next_cursor,
    )


def create_team(db: Session, actor_id: str, name: str) -> TeamRead:
    team = Team(name=name, created_by_id=actor_id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=actor_id, role=TeamRole.OWNER))
    access = TeamAccess(team, actor_id, TeamRole.OWNER)
    access.record(db, "team.created", team.id)
    db.commit()
    return access.read()


def rename_team(db: Session, access: TeamAccess, name: str) -> TeamRead:
    if name != access.team.name:
        access.team.name = name
        access.record(db, "team.renamed", access.team.id)
    db.commit()
    return access.read()


def update_avatar(db: Session, access: TeamAccess, image: bytes | None) -> TeamRead:
    if set_avatar(access.team, image):
        action = "team.avatarRemoved" if image is None else "team.avatarUpdated"
        access.record(db, action, access.team.id)
    db.commit()
    return access.read()


def update_profile_visibility(db: Session, access: TeamAccess, public: bool) -> TeamRead:
    if public != access.team.profile_public:
        access.team.profile_public = public
        action = "team.profilePublished" if public else "team.profileHidden"
        access.record(db, action, access.team.id)
    db.commit()
    return access.read()


def read_avatar(db: Session, team_id: str, version: str, viewer_id: str | None) -> bytes:
    visible = public_profile_visible()
    if viewer_id is not None:
        visible |= Team.id.in_(_active_memberships(viewer_id).with_only_columns(Team.id))
    image = db.scalar(
        select(Team.avatar_image).where(Team.id == team_id, Team.avatar_digest == version, visible)
    )
    if image is None:
        raise HTTPException(404, msg("profile.avatarNotFound"))
    return image


def list_members(db: Session, team_id: str, cursor: str | None, limit: int) -> TeamMemberPage:
    query = (
        select(User, TeamMember.role)
        .join(TeamMember, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id, User.deleted_at.is_(None))
        .options(load_only(User.id, User.username, User.nickname, User.avatar_digest))
    )
    if position := decode_cursor(cursor, 1):
        query = query.where(User.id > position[0])
    rows = db.execute(query.order_by(User.id).limit(limit + 1)).all()
    items, next_cursor = split_page(rows, limit, lambda row: (row[0].id,))
    return TeamMemberPage(
        items=[
            TeamMemberRead(id=account.id, role=role, **AuthorRead.from_user(account).model_dump())
            for account, role in items
        ],
        next_cursor=next_cursor,
    )


def _manageable(access: TeamAccess, role: TeamRole) -> bool:
    return role != TeamRole.OWNER and (
        access.role == TeamRole.OWNER or not role.permits(TeamRole.MANAGER)
    )


def set_member(db: Session, access: TeamAccess, account: User, role: TeamRole) -> None:
    db.refresh(account)
    if account.deleted_at is not None:
        raise HTTPException(404, msg("grants.unknownAccount"))
    target = account.id
    member = db.get(TeamMember, (access.team.id, target))
    if not _manageable(access, role) or (member and not _manageable(access, member.role)):
        raise HTTPException(403, msg("team.permissionDenied"))
    if member is None:
        db.add(TeamMember(team_id=access.team.id, user_id=target, role=role))
        access.record(db, "member.added", target)
    elif member.role != role:
        member.role = role
        access.record(db, "member.roleChanged", target)
    db.commit()


def remove_member(db: Session, access: TeamAccess, target: str) -> None:
    leaving = target == access.actor_id
    if not leaving and not access.role.permits(TeamRole.MANAGER):
        raise HTTPException(403, msg("team.permissionDenied"))
    member = db.get(TeamMember, (access.team.id, target))
    if member is None:
        return
    if leaving and member.role == TeamRole.OWNER:
        raise HTTPException(409, msg("team.transferFirst"))
    if not leaving and not _manageable(access, member.role):
        raise HTTPException(403, msg("team.permissionDenied"))
    db.delete(member)
    access.record(db, "member.left" if leaving else "member.removed", target)
    db.commit()


def transfer_team(db: Session, access: TeamAccess, recipient: str) -> TeamRead:
    successor = db.get(TeamMember, (access.team.id, recipient))
    user = db.get(User, recipient)
    if successor is None or user is None or user.deleted_at is not None:
        raise HTTPException(404, msg("team.memberUnavailable"))
    if successor.role == TeamRole.OWNER:
        return access.read()
    incumbent = db.get(TeamMember, (access.team.id, access.actor_id))
    assert incumbent is not None
    incumbent.role = TeamRole.MANAGER
    db.flush()
    successor.role = TeamRole.OWNER
    access.record(db, "team.transferred", recipient)
    db.commit()
    return TeamRead.from_team(access.team, TeamRole.MANAGER)


def archive_team(db: Session, access: TeamAccess) -> None:
    # 提交、重试和恢复排队都使用同一个团队写锁。
    if db.scalar(
        select(Task.id)
        .where(Task.team_id == access.team.id, Task.visible(), Task.status.in_(Status.ACTIVE))
        .limit(1)
    ):
        raise HTTPException(409, msg("team.finishTasksBeforeArchive"))
    access.team.archived_at = now_ms()
    access.record(db, "team.archived", access.team.id)
    db.commit()


def restore_team(db: Session, team_id: str, actor_id: str) -> TeamRead:
    write_lock(db, Team, team_id)
    row = db.execute(
        _memberships(actor_id)
        .where(Team.id == team_id, TeamMember.role == TeamRole.OWNER)
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, msg("team.unavailable"))
    access = TeamAccess(row[0], actor_id, row.role)
    if access.team.archived_at is not None:
        access.team.archived_at = None
        access.record(db, "team.restored", team_id)
    db.commit()
    return access.read()


def ensure_account_can_leave_teams(db: Session, actor_id: str) -> None:
    owner = db.scalar(
        select(TeamMember.team_id)
        .join(Team, Team.id == TeamMember.team_id)
        .where(
            TeamMember.user_id == actor_id,
            TeamMember.role == TeamRole.OWNER,
            Team.archived_at.is_(None),
        )
        .limit(1)
    )
    if owner is not None:
        raise HTTPException(409, msg("team.transferFirst"))
