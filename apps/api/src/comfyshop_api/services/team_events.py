"""读取团队历史记录及仍可在该空间识别的对象名称。"""

from collections import defaultdict

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from comfyshop_api.models import (
    Artifact,
    Asset,
    Execution,
    Machine,
    MachineLink,
    Project,
    Task,
    TeamEvent,
    User,
    Work,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import TeamEventCategory, TeamEventPage, TeamEventRead
from comfyshop_api.services.teams import TeamAccess
from comfyshop_api.services.workflows import team_visible_workflow

_TARGET_CATEGORIES = {
    "team.transferred": "member",
    "workflow.parametersChanged": "version",
    "machine.linkApproved": "link",
}


def _target_category(event: TeamEvent) -> str:
    return _TARGET_CATEGORIES.get(event.action, event.action.partition(".")[0])


def _target_names(
    db: Session, access: TeamAccess, events: list[TeamEvent]
) -> dict[tuple[str, str], str]:
    ids: defaultdict[str, list[str]] = defaultdict(list)
    for event in events:
        ids[_target_category(event)].append(event.record_id)
    team_id = access.team.id
    queries = {
        "project": select(Project.id, Project.name).where(
            Project.id.in_(ids["project"]), Project.team_id == team_id
        ),
        "member": select(User.id, func.coalesce(User.nickname, User.username)).where(
            User.id.in_(ids["member"]), User.deleted_at.is_(None)
        ),
        "workflow": select(Workflow.id, Workflow.name).where(
            Workflow.id.in_(ids["workflow"]), Workflow.team_id == team_id
        ),
        "version": select(WorkflowVersion.id, Workflow.name)
        .join(Workflow, Workflow.id == WorkflowVersion.workflow_id)
        .where(WorkflowVersion.id.in_(ids["version"]), Workflow.team_id == team_id),
        "favorite": select(Workflow.id, Workflow.name).where(
            Workflow.id.in_(ids["favorite"]), team_visible_workflow(team_id)
        ),
        "machine": select(Machine.id, Machine.name).where(
            Machine.id.in_(ids["machine"]), Machine.team_id == team_id
        ),
        "link": select(MachineLink.id, MachineLink.name).where(
            MachineLink.id.in_(ids["link"]), MachineLink.team_id == team_id
        ),
        "asset": select(Asset.id, Asset.filename).where(
            Asset.id.in_(ids["asset"]), Asset.team_id == team_id
        ),
        "work": select(Work.id, Work.title).where(
            Work.id.in_(ids["work"]), Work.team_id == team_id
        ),
        "task": select(Task.id, Task.workflow_name).where(
            Task.id.in_(ids["task"]), Task.team_id == team_id
        ),
        "execution": select(Execution.id, Task.workflow_name)
        .join(Task, Task.id == Execution.task_id)
        .where(Execution.id.in_(ids["execution"]), Task.team_id == team_id),
        "artifact": select(Artifact.id, Artifact.filename)
        .join(Task, Task.id == Artifact.task_id)
        .where(Artifact.id.in_(ids["artifact"]), Task.team_id == team_id),
    }
    names = {("team", team_id): access.team.name}
    for category, query in queries.items():
        if ids[category]:
            names.update(
                ((category, record_id), name) for record_id, name in db.execute(query) if name
            )
    return names


def list_events(
    db: Session,
    access: TeamAccess,
    *,
    actor: str | None,
    category: TeamEventCategory | None,
    created_from: int | None,
    created_before: int | None,
    cursor: str | None,
    limit: int,
) -> TeamEventPage:
    query = (
        select(TeamEvent, User.username, User.nickname, User.deleted_at)
        .join(User, User.id == TeamEvent.actor_id)
        .where(TeamEvent.team_id == access.team.id)
    )
    if actor and (search := actor.strip()):
        query = query.where(
            User.deleted_at.is_(None),
            or_(
                User.username.icontains(search, autoescape=True),
                User.nickname.icontains(search, autoescape=True),
            ),
        )
    if category:
        query = query.where(TeamEvent.action.startswith(f"{category}."))
    if created_from is not None:
        query = query.where(TeamEvent.created_at >= created_from)
    if created_before is not None:
        query = query.where(TeamEvent.created_at < created_before)
    if position := decode_cursor(cursor, 2):
        query = query.where(tuple_(TeamEvent.created_at, TeamEvent.id) < tuple(position))
    rows = db.execute(
        query.order_by(TeamEvent.created_at.desc(), TeamEvent.id.desc()).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(rows, limit, lambda row: (row[0].created_at, row[0].id))
    targets = _target_names(db, access, [row[0] for row in items])
    return TeamEventPage(
        items=[
            TeamEventRead(
                id=event.id,
                action=event.action,
                actor_name=(nickname or username) if deleted_at is None else None,
                actor_username=username if deleted_at is None else None,
                record_id=event.record_id,
                target=targets.get((_target_category(event), event.record_id)),
                created=event.created_at,
            )
            for event, username, nickname, deleted_at in items
        ],
        next_cursor=next_cursor,
    )
