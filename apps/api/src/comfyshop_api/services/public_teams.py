"""团队主页与公开身份共用的可见规则。"""

from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import ColumnElement, SQLColumnExpression, select
from sqlalchemy.orm import Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import Team, Work, Workflow
from comfyshop_api.schemas import PublicTeamIdentity, PublicTeamRead, team_avatar_url
from comfyshop_api.services.public_catalog import public_catalog_workflow, public_work_condition


def _has_workflows() -> ColumnElement[bool]:
    return (
        select(Workflow.id)
        .where(Workflow.team_id == Team.id, public_catalog_workflow())
        .correlate(Team)
        .exists()
    )


def _has_works() -> ColumnElement[bool]:
    return (
        select(Work.id)
        .join(Workflow)
        .where(Work.team_id == Team.id, public_work_condition())
        .correlate(Team)
        .exists()
    )


def public_profile_visible() -> ColumnElement[bool]:
    return (
        Team.profile_public.is_(True)
        & Team.archived_at.is_(None)
        & (_has_workflows() | _has_works())
    )


def from_public_team(
    team_column: SQLColumnExpression[str | None], team_id: str
) -> ColumnElement[bool]:
    return team_column.in_(select(Team.id).where(Team.id == team_id, public_profile_visible()))


def public_team_identity(team: Team) -> PublicTeamIdentity:
    return PublicTeamIdentity(id=team.id, name=team.name, avatar_url=team_avatar_url(team))


def public_team_identities(
    db: Session, team_ids: Iterable[str | None]
) -> dict[str, PublicTeamIdentity]:
    ids = {team_id for team_id in team_ids if team_id}
    if not ids:
        return {}
    teams = db.scalars(select(Team).where(Team.id.in_(ids), public_profile_visible()))
    return {team.id: public_team_identity(team) for team in teams}


def read_public_team(db: Session, team_id: str) -> PublicTeamRead:
    row = db.execute(
        select(Team, _has_workflows().label("has_workflows")).where(
            Team.id == team_id, public_profile_visible()
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, msg("team.publicProfileUnavailable"))
    team, has_workflows = row
    return PublicTeamRead(**public_team_identity(team).model_dump(), has_workflows=has_workflows)
