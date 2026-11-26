"""个人、团队及只读共享空间共用的项目入口。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from comfyshop_api.api.teams import TeamEditor, TeamManager, TeamReader
from comfyshop_api.api.workspace_shares import SignedInWorkspaceReader
from comfyshop_api.schemas import ProjectArchive, ProjectCreate, ProjectPage, ProjectRead
from comfyshop_api.security import DB, CurrentUser
from comfyshop_api.services.projects import (
    ProjectMaterial,
    active_project,
    change_project_material,
    create_project,
    list_projects,
    project_read,
    scoped_project,
    set_project_archived,
    set_project_deleted,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def projects(
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    search: Annotated[str, Query(max_length=80)] = "",
    archived: bool = False,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> ProjectPage:
    return list_projects(
        db, owner_id, team.team.id if team else None, search, cursor, limit, archived=archived
    )


@router.post("", status_code=201)
def add_project(body: ProjectCreate, db: DB, user: CurrentUser, team: TeamEditor) -> ProjectRead:
    return create_project(db, user.id, team, body)


@router.get("/{project_id}")
def get_project(
    project_id: UUID, db: DB, team: TeamReader, owner_id: SignedInWorkspaceReader
) -> ProjectRead:
    return project_read(
        scoped_project(db, str(project_id), owner_id, team.team.id if team else None)
    )


@router.put("/{project_id}")
def edit_project(
    project_id: UUID, body: ProjectCreate, db: DB, user: CurrentUser, team: TeamEditor
) -> ProjectRead:
    project = active_project(db, str(project_id), user.id, team.team.id if team else None)
    return update_project(db, project, body, team)


@router.put("/{project_id}/archive")
def archive_project(
    project_id: UUID, body: ProjectArchive, db: DB, user: CurrentUser, team: TeamManager
) -> ProjectRead:
    project = scoped_project(db, str(project_id), user.id, team.team.id if team else None)
    return set_project_archived(db, project, body.archived, team)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, db: DB, user: CurrentUser, team: TeamManager) -> None:
    project = scoped_project(
        db, str(project_id), user.id, team.team.id if team else None, include_deleted=True
    )
    set_project_deleted(db, project, True, team)


@router.post("/{project_id}/restore")
def restore_project(project_id: UUID, db: DB, user: CurrentUser, team: TeamManager) -> ProjectRead:
    project = scoped_project(
        db, str(project_id), user.id, team.team.id if team else None, include_deleted=True
    )
    set_project_deleted(db, project, False, team)
    return project_read(project)


@router.put("/{project_id}/{kind}/{record_id}", status_code=204)
def link_project_material(
    project_id: UUID,
    kind: ProjectMaterial,
    record_id: UUID,
    db: DB,
    user: CurrentUser,
    team: TeamEditor,
) -> None:
    project = active_project(db, str(project_id), user.id, team.team.id if team else None)
    change_project_material(db, project, kind, str(record_id), True, team)


@router.delete("/{project_id}/{kind}/{record_id}", status_code=204)
def unlink_project_material(
    project_id: UUID,
    kind: ProjectMaterial,
    record_id: UUID,
    db: DB,
    user: CurrentUser,
    team: TeamEditor,
) -> None:
    project = active_project(db, str(project_id), user.id, team.team.id if team else None)
    change_project_material(db, project, kind, str(record_id), False, team)
