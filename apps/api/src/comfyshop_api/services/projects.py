"""空间内的项目和资料引用。任务是结果与作品的项目归属来源。"""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import ColumnElement, or_, select, tuple_
from sqlalchemy.orm import Session

from comfyshop_api.core.i18n import msg
from comfyshop_api.models import (
    Artifact,
    Asset,
    Execution,
    MediaObject,
    Project,
    ProjectAsset,
    ProjectWorkflow,
    Status,
    Task,
    Workflow,
    now_ms,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    MediaRead,
    ProjectCreate,
    ProjectListItem,
    ProjectPage,
    ProjectRead,
)
from comfyshop_api.security import owned_record, workspace_records
from comfyshop_api.services.media_records import artifact_media, asset_read
from comfyshop_api.services.public_catalog import public_catalog_workflow
from comfyshop_api.services.teams import TeamAccess

type ProjectMaterial = Literal["workflows", "assets"]


def scoped_project(
    db: Session,
    project_id: str,
    owner_id: str,
    team_id: str | None,
    *,
    include_deleted: bool = False,
) -> Project:
    project = owned_record(
        db, Project, project_id, owner_id, msg("project.notFound"), team_id=team_id
    )
    if project.deleted_at is not None and not include_deleted:
        raise HTTPException(404, msg("project.notFound"))
    return project


def active_project(db: Session, project_id: str, owner_id: str, team_id: str | None) -> Project:
    project = scoped_project(db, project_id, owner_id, team_id)
    if project.archived_at is not None:
        raise HTTPException(409, msg("project.archived"))
    return project


def active_project_id(db: Session, project_id: str | None) -> str | None:
    """项目关闭后，历史批次仍保留归属，新任务只沿用进行中的项目。"""
    if project_id is None:
        return None
    return db.scalar(
        select(Project.id).where(
            Project.id == project_id, Project.visible(), Project.archived_at.is_(None)
        )
    )


def project_read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        created=project.created_at,
        archived_at=project.archived_at,
    )


def _project_covers(
    db: Session, ids: list[str], owner_id: str, team_id: str | None
) -> dict[str, MediaRead]:
    if not ids:
        return {}
    result_cover = (
        select(Artifact.id)
        .join(
            Execution,
            (Execution.id == Artifact.execution_id) & (Execution.task_id == Artifact.task_id),
        )
        .join(Task, Task.id == Execution.task_id)
        .join(MediaObject, MediaObject.sha256 == Artifact.sha256)
        .where(
            Task.project_id == Project.id,
            workspace_records(Task.owner_id, Task.team_id, owner_id, team_id),
            Execution.status == Status.SUCCEEDED,
            Artifact.visible(),
            Artifact.content_type.startswith("image/") | Artifact.content_type.startswith("video/"),
            MediaObject.width.is_not(None),
            MediaObject.height.is_not(None),
        )
        .order_by(
            Execution.created_at.desc(),
            Execution.id.desc(),
            Artifact.content_type.startswith("image/").desc(),
            Artifact.output_index,
            Artifact.id,
        )
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    result_rows = db.execute(
        select(Project.id, Artifact)
        .join(Artifact, Artifact.id == result_cover)
        .where(Project.id.in_(ids))
    ).tuples()
    covers = {project_id: artifact_media(artifact) for project_id, artifact in result_rows}
    remaining = [project_id for project_id in ids if project_id not in covers]
    if not remaining:
        return covers
    reference_cover = (
        select(ProjectAsset.asset_id)
        .join(Asset, Asset.id == ProjectAsset.asset_id)
        .join(MediaObject, MediaObject.sha256 == Asset.sha256)
        .where(
            ProjectAsset.project_id == Project.id,
            workspace_records(Asset.owner_id, Asset.team_id, owner_id, team_id),
            Asset.saved_at.is_not(None),
            Asset.content_type.startswith("image/") | Asset.content_type.startswith("video/"),
            MediaObject.width.is_not(None),
            MediaObject.height.is_not(None),
        )
        .order_by(Asset.saved_at.desc(), Asset.id.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    reference_rows = db.execute(
        select(Project.id, Asset)
        .join(Asset, Asset.id == reference_cover)
        .where(Project.id.in_(remaining))
    ).tuples()
    covers.update((project_id, asset_read(asset).media) for project_id, asset in reference_rows)
    return covers


def list_projects(
    db: Session,
    owner_id: str,
    team_id: str | None,
    search: str,
    cursor: str | None,
    limit: int,
    *,
    archived: bool,
) -> ProjectPage:
    query = select(Project).where(
        workspace_records(Project.owner_id, Project.team_id, owner_id, team_id),
        Project.visible(),
        Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None),
    )
    if text := search.strip():
        query = query.where(Project.name.icontains(text, autoescape=True))
    if position := decode_cursor(cursor, 2):
        query = query.where(tuple_(Project.created_at, Project.id) < tuple(position))
    rows = db.scalars(query.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit + 1))
    items, next_cursor = split_page(list(rows), limit, lambda item: (item.created_at, item.id))
    covers = _project_covers(db, [project.id for project in items], owner_id, team_id)
    return ProjectPage(
        items=[
            ProjectListItem(**project_read(project).model_dump(), cover=covers.get(project.id))
            for project in items
        ],
        next_cursor=next_cursor,
    )


def create_project(
    db: Session, owner_id: str, team: TeamAccess | None, body: ProjectCreate
) -> ProjectRead:
    project = Project(
        owner_id=owner_id,
        team_id=team.team.id if team else None,
        name=body.name,
        description=body.description,
    )
    db.add(project)
    db.flush()
    _save_project_change(db, project, team, "project.created")
    return project_read(project)


def _save_project_change(
    db: Session, project: Project, team: TeamAccess | None, action: str
) -> None:
    if team:
        team.record(db, action, project.id)
    db.commit()


def update_project(
    db: Session, project: Project, body: ProjectCreate, team: TeamAccess | None
) -> ProjectRead:
    if (project.name, project.description) != (body.name, body.description):
        project.name = body.name
        project.description = body.description
        _save_project_change(db, project, team, "project.updated")
    return project_read(project)


def set_project_archived(
    db: Session, project: Project, archived: bool, team: TeamAccess | None
) -> ProjectRead:
    if (project.archived_at is not None) != archived:
        project.archived_at = now_ms() if archived else None
        _save_project_change(
            db, project, team, "project.archived" if archived else "project.unarchived"
        )
    return project_read(project)


def set_project_deleted(
    db: Session, project: Project, deleted: bool, team: TeamAccess | None
) -> None:
    changed = project.mark_deleted() if deleted else project.restore()
    if changed:
        _save_project_change(
            db, project, team, "project.deleted" if deleted else "project.restored"
        )


def project_workflow_scope(project: Project) -> ColumnElement[bool]:
    return or_(
        workspace_records(Workflow.owner_id, Workflow.team_id, project.owner_id, project.team_id),
        public_catalog_workflow(),
    )


def change_project_material(
    db: Session,
    project: Project,
    kind: ProjectMaterial,
    record_id: str,
    linked: bool,
    team: TeamAccess | None,
) -> None:
    key = (project.id, record_id)
    if kind == "workflows":
        existing = db.get(ProjectWorkflow, key)
        if linked and not existing:
            available = db.scalar(
                select(Workflow.id).where(
                    Workflow.id == record_id, Workflow.visible(), project_workflow_scope(project)
                )
            )
            if not available:
                raise HTTPException(404, msg("workflow.notFound"))
            db.add(ProjectWorkflow(project_id=project.id, workflow_id=record_id))
    else:
        existing = db.get(ProjectAsset, key)
        if linked and not existing:
            available = db.scalar(
                select(Asset.id).where(
                    Asset.id == record_id,
                    Asset.saved_at.is_not(None),
                    workspace_records(
                        Asset.owner_id, Asset.team_id, project.owner_id, project.team_id
                    ),
                )
            )
            if not available:
                raise HTTPException(404, msg("asset.notFound"))
            db.add(ProjectAsset(project_id=project.id, asset_id=record_id))
    if linked == bool(existing):
        return
    if existing:
        db.delete(existing)
    _save_project_change(db, project, team, "project.materialsChanged")
