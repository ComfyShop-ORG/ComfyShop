"""作品接口，管理已经选定的执行成品及其公开状态。"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select, tuple_

from comfyshop_api.api.teams import TeamManager, TeamReader
from comfyshop_api.api.workspace_shares import WorkspaceReader
from comfyshop_api.core.categories import WorkflowCategoryFilter
from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.models import (
    Artifact,
    Execution,
    Task,
    User,
    Work,
    WorkArtifact,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    ArtifactPage,
    CoverUpdate,
    ReplayRead,
    TaskInputsRead,
    WorkCreate,
    WorkPage,
    WorkRead,
)
from comfyshop_api.security import DB, Config, CurrentUser, MaybeSession, workspace_records
from comfyshop_api.services.inputs import recorded_input
from comfyshop_api.services.media_records import artifact_read, asset_read
from comfyshop_api.services.media_responses import (
    THUMBNAIL_RESPONSES,
    original_response,
    thumbnail_response,
)
from comfyshop_api.services.projects import active_project_id, scoped_project
from comfyshop_api.services.public_catalog import public_work_condition
from comfyshop_api.services.public_teams import from_public_team
from comfyshop_api.services.workflows import replay_workflow_read
from comfyshop_api.services.works import (
    owned_work,
    publish_work,
    readable_work,
    readable_work_asset,
    readable_work_cover,
    restore_deleted_work,
    update_work_cover,
    work_assets,
    work_reads,
)
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE

router = APIRouter(prefix="/works", tags=["works"])


# `artifact_ids` 只选本人这次成功执行的成品，未选中的图片可单独作封面。封面是视频时可用
# `cover_frame_ms` 指定取哪一刻的画面，时间超出视频长度返回 422。
# `share_parameters` 公开标量输入，`share_assets` 公开整套输入。相同发布编号和内容可重试。
@router.post("", status_code=201)
def create_work(
    body: WorkCreate,
    db: DB,
    user: CurrentUser,
    team: TeamManager,
    response: Response,
    config: Config,
) -> WorkRead:
    work, created = publish_work(db, user.id, body, config, team=team)
    if not created:
        response.status_code = 200
    return work_reads(db, [work])[0]


# author 按作者账号名筛选，用于作者页面。
@router.get("", response_model=WorkPage)
def list_works(
    db: DB,
    team: TeamReader,
    viewer_id: WorkspaceReader,
    scope: Literal["public", "mine"] = "public",
    category: WorkflowCategoryFilter = "all",
    workflow_id: str | None = None,
    version_id: str | None = None,
    current_version_only: bool = False,
    author: Annotated[str, Query(max_length=32)] = "",
    public_team_id: UUID | None = None,
    project_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
):
    query = select(Work).join(Workflow)
    if public_team_id:
        if scope != "public" or team:
            raise HTTPException(422, msg("team.publicFilterRequiresCatalog"))
        query = query.where(from_public_team(Work.team_id, str(public_team_id)))
    if scope == "mine":
        if viewer_id is None:
            raise HTTPException(401, msg("workflow.signInToContinue"))
        query = query.where(
            workspace_records(
                Work.owner_id, Work.team_id, viewer_id, team.team.id if team else None
            ),
            Work.visible(),
        )
    else:
        if project_id:
            raise HTTPException(422, msg("project.workspaceFilterRequired"))
        query = query.where(public_work_condition())
    if project_id and viewer_id is not None:
        project = scoped_project(db, str(project_id), viewer_id, team.team.id if team else None)
        query = (
            query.join(Execution, Execution.id == Work.execution_id)
            .join(Task, Task.id == Execution.task_id)
            .where(Task.project_id == project.id)
        )
    if category != "all":
        query = query.where(Workflow.category == category)
    if workflow_id:
        query = query.where(Work.workflow_id == workflow_id)
    if version_id:
        query = query.where(Work.version_id == version_id)
    if current_version_only:
        query = query.where(Work.version_id == Workflow.published_version_id)
    if author.strip():
        query = query.where(
            Work.owner_id.in_(select(User.id).where(User.username == author.strip()))
        )
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(Work.created_at, Work.id) < tuple(position))
    records = list(
        db.scalars(query.order_by(Work.created_at.desc(), Work.id.desc()).limit(limit + 1))
    )
    items, next_cursor = split_page(records, limit, lambda work: (work.created_at, work.id))
    return WorkPage(items=work_reads(db, list(items)), next_cursor=next_cursor)


@router.get("/{work_id}")
def get_work(work_id: str, db: DB, team: TeamReader, viewer_id: WorkspaceReader) -> WorkRead:
    return work_reads(
        db, [readable_work(db, work_id, viewer_id, team_id=team.team.id if team else None)]
    )[0]


@router.put("/{work_id}/cover")
def set_work_cover(
    work_id: str, body: CoverUpdate, db: DB, user: CurrentUser, team: TeamManager, config: Config
) -> WorkRead:
    work = update_work_cover(
        db, work_id, user.id, body, config, team_id=team.team.id if team else None
    )
    if team:
        team.record(db, "work.coverChanged", work.id)
    db.commit()
    return work_reads(db, [work])[0]


@router.get(
    "/{work_id}/cover/{sha256}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES
)
async def work_cover_thumbnail(
    work_id: str,
    sha256: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: Annotated[int | None, Query(ge=1, le=MAX_THUMBNAIL_SIZE)] = None,
) -> Response:
    media = await run_in_threadpool(
        readable_work_cover, db, work_id, session.user_id if session else None, sha256
    )
    return await thumbnail_response(request, media, config, size)


@router.get("/{work_id}/artifacts", response_model=ArtifactPage)
def work_artifacts(
    work_id: str,
    db: DB,
    team: TeamReader,
    viewer_id: WorkspaceReader,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
):
    work = readable_work(db, work_id, viewer_id, team_id=team.team.id if team else None)
    execution = db.get(Execution, work.execution_id)
    if execution is None:
        raise HTTPException(404, msg("workflow.runNotFound"))
    task = db.get(Task, execution.task_id)
    if task is None:
        raise HTTPException(404, msg("task.notFound"))
    query = select(WorkArtifact, Artifact).join(Artifact).where(WorkArtifact.work_id == work.id)
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(WorkArtifact.position, Artifact.id) > tuple(position))
    records = db.execute(query.order_by(WorkArtifact.position, Artifact.id).limit(limit + 1)).all()
    items, next_cursor = split_page(records, limit, lambda row: (row[0].position, row[1].id))
    return ArtifactPage(items=[artifact_read(a, task) for _, a in items], next_cursor=next_cursor)


# 作者发布时选择公开的参数、字段名称和参考素材。
@router.get("/{work_id}/inputs")
def work_inputs(
    work_id: str, db: DB, team: TeamReader, viewer_id: WorkspaceReader, language: Language
) -> TaskInputsRead:
    work = readable_work(db, work_id, viewer_id, team_id=team.team.id if team else None)
    execution = db.get(Execution, work.execution_id)
    task = db.get(Task, execution.task_id) if execution else None
    version = db.scalar(select(WorkflowVersion.number).where(WorkflowVersion.id == work.version_id))
    if task is None or version is None:
        raise HTTPException(404, msg("work.notFound"))
    return TaskInputsRead(
        version=version,
        fields=[
            recorded_input(field, language)
            for field in task.input_schema.get("fields", [])
            if field["id"] in work.input_values
        ],
        assets=[asset_read(asset) for asset in work_assets(db, work.id)],
    )


@router.get("/{work_id}/assets/{asset_id}/file", response_class=FileResponse)
def work_asset_file(
    work_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    download: bool = False,
) -> Response:
    asset = readable_work_asset(db, work_id, asset_id, session.user_id if session else None)
    return original_response(request, config.media_storage, asset, download)


@router.get(
    "/{work_id}/assets/{asset_id}/thumbnail", response_class=Response, responses=THUMBNAIL_RESPONSES
)
async def work_asset_thumbnail(
    work_id: str,
    asset_id: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: Annotated[
        int | None, Query(ge=1, le=MAX_THUMBNAIL_SIZE, description="目标长边像素")
    ] = None,
) -> Response:
    asset = await run_in_threadpool(
        readable_work_asset, db, work_id, asset_id, session.user_id if session else None
    )
    return await thumbnail_response(request, asset, config, size)


@router.delete("/{work_id}", status_code=204)
def unpublish_work(work_id: str, db: DB, user: CurrentUser, team: TeamManager) -> Response:
    work = owned_work(db, work_id, user.id, team_id=team.team.id if team else None)
    if work.published:
        work.published = False
        if team:
            team.record(db, "work.unpublished", work.id)
        db.commit()
    return Response(status_code=204)


# DELETE /works/{work_id} 已用于取消公开。单独提供删除记录的操作。
@router.post("/{work_id}/delete", status_code=204)
def delete_work(work_id: str, db: DB, user: CurrentUser, team: TeamManager) -> Response:
    work = owned_work(
        db, work_id, user.id, team_id=team.team.id if team else None, include_deleted=True
    )
    if work.mark_deleted():
        if team:
            team.record(db, "work.deleted", work.id)
        db.commit()
    return Response(status_code=204)


# 撤销删除。作品恢复删除前的公开状态。
@router.post("/{work_id}/restore", status_code=204)
def restore_work(work_id: str, db: DB, user: CurrentUser, team: TeamManager) -> Response:
    work = owned_work(
        db, work_id, user.id, team_id=team.team.id if team else None, include_deleted=True
    )
    changed = work.deleted_at is not None
    restore_deleted_work(db, work)
    if team and changed:
        team.record(db, "work.restored", work.id)
    db.commit()
    return Response(status_code=204)


@router.get("/{work_id}/replay")
def replay_work(
    work_id: str, db: DB, user: CurrentUser, team: TeamReader, language: Language
) -> ReplayRead:
    team_id = team.team.id if team else None
    work = readable_work(db, work_id, user.id, team_id=team_id)
    project_id = db.scalar(
        select(Task.project_id)
        .join(Execution, Execution.task_id == Task.id)
        .where(
            Execution.id == work.execution_id,
            workspace_records(Task.owner_id, Task.team_id, user.id, team_id),
        )
    )
    return ReplayRead(
        workflow=replay_workflow_read(
            db, work.workflow_id, work.version_id, user.id, language, team_id=team_id
        ),
        source_work_id=work.id,
        project_id=active_project_id(db, project_id),
    )
