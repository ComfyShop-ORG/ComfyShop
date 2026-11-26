"""工作流接口，提供导入、版本浏览、表单、发布以及封面和示例管理。"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import exists, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError

from comfyshop_api.api.teams import TeamEditor, TeamManager, TeamReader, team_editor
from comfyshop_api.api.workspace_shares import SignedInWorkspaceReader, WorkspaceReader
from comfyshop_api.core.categories import WorkflowCategoryFilter
from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.models import (
    Execution,
    Favorite,
    Machine,
    ProjectWorkflow,
    Status,
    Task,
    TeamFavorite,
    User,
    Workflow,
    WorkflowVersion,
    now_ms,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    GraphRead,
    ReferenceImport,
    WorkflowCoverUpdate,
    WorkflowCreate,
    WorkflowForm,
    WorkflowFormData,
    WorkflowInputContext,
    WorkflowInputQuery,
    WorkflowPage,
    WorkflowParameterDisplay,
    WorkflowParameterLayoutUpdate,
    WorkflowRead,
    WorkflowUpdate,
    WorkflowVersionRead,
    WorkflowVersions,
    WorkspaceRead,
)
from comfyshop_api.security import (
    COOKIE_NAME,
    DB,
    Config,
    CurrentUser,
    LockedWriter,
    MaybeSession,
    Writer,
    can_import_official_workflows,
    check_origin,
    current_user,
    digest,
    is_official_worker,
    protect_write,
    require_official_import,
    workspace_records,
)
from comfyshop_api.services.connections import import_source
from comfyshop_api.services.cost_estimates import can_estimate_cost
from comfyshop_api.services.executions import owned_execution
from comfyshop_api.services.inpainting import inpaint_targets
from comfyshop_api.services.inputs import (
    form_for,
    localize_form,
    normalize_float_defaults,
    official_form_for,
    parameter_controls_for,
    replay_defaults,
    update_parameter_layout,
)
from comfyshop_api.services.machines import bearer, owned_machine
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.media_responses import THUMBNAIL_RESPONSES, thumbnail_response
from comfyshop_api.services.media_uploads import upload_media
from comfyshop_api.services.projects import project_workflow_scope, scoped_project
from comfyshop_api.services.public_catalog import public_catalog_workflow
from comfyshop_api.services.public_teams import from_public_team, public_team_identities
from comfyshop_api.services.worker_types import OFFICIAL, worker_type
from comfyshop_api.services.workflows import (
    apply_workflow_update,
    browse_version_id,
    can_read_workflow_drafts,
    copy_team_workflow,
    favorite_workflow_ids,
    import_workflow,
    is_service_manifest,
    owned_workflow,
    readable_version,
    readable_workflow,
    readable_workflow_cover,
    store_official_workflow_cover,
    team_visible_workflow,
    update_workflow_cover,
    version_workflow_read,
    visible_version,
    workflow_covers,
    workflow_graph,
    workflow_read,
    workflow_stats,
)
from comfyshop_api.services.works import readable_work, work_assets
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE

router = APIRouter(tags=["workflows"])


def form_machine(db: DB, machine_id: str, user_id: str, *, team_id: str | None = None) -> Machine:
    machine = owned_machine(db, machine_id, user_id, team_id=team_id)
    if machine.revoked_at:
        raise HTTPException(404, msg("machine.notFound"))
    return machine


@router.post("/workflows/from-connection", status_code=201)
async def add_reference(
    body: ReferenceImport,
    request: Request,
    db: DB,
    user: LockedWriter,
    team: TeamEditor,
    config: Config,
    language: Language,
) -> WorkflowRead:
    workflow, version = await import_source(
        db,
        user,
        body,
        config,
        session_hash=digest(request.cookies[COOKIE_NAME]),
        team_id=team.team.id if team else None,
    )
    return workflow_read(workflow, version=version, language=language)


@router.get("/workflows/{workflow_id}/inputs")
def workflow_inputs(
    workflow_id: str,
    db: DB,
    user: CurrentUser,
    team: TeamReader,
    query: Annotated[WorkflowInputQuery, Query()],
    language: Language,
    config: Config,
) -> WorkflowForm:
    team_id = team.team.id if team else None
    workflow = readable_workflow(db, workflow_id, user.id, team_id=team_id)
    version = readable_version(db, workflow, query.version_id, user.id, team_id=team_id)
    machine = form_machine(db, query.machine_id, user.id, team_id=team_id)
    form = form_for(
        version,
        machine,
        include_original_defaults=can_read_workflow_drafts(workflow, user.id, team_id),
    )
    return _input_defaults(db, form, user, query, language, version, config, team_id=team_id)


@router.get("/workflows/{workflow_id}/service-inputs")
def service_workflow_inputs(
    workflow_id: str,
    db: DB,
    user: CurrentUser,
    team: TeamReader,
    query: Annotated[WorkflowInputContext, Query()],
    language: Language,
    config: Config,
) -> WorkflowFormData:
    team_id = team.team.id if team else None
    workflow = readable_workflow(db, workflow_id, user.id, team_id=team_id)
    version = readable_version(db, workflow, query.version_id, user.id, team_id=team_id)
    if worker_type(version.worker_kind).connection != "platform":
        raise HTTPException(404, msg("workflow.notFound"))
    form = official_form_for(
        version, include_original_defaults=can_read_workflow_drafts(workflow, user.id, team_id)
    )
    form.cost_estimate = can_estimate_cost(version, config)
    return _input_defaults(db, form, user, query, language, version, config, team_id=team_id)


def _input_defaults[T: WorkflowFormData](
    db: DB,
    form: T,
    user: User,
    query: WorkflowInputContext,
    language: str,
    version: WorkflowVersion,
    config: Config,
    *,
    team_id: str | None = None,
) -> T:
    if query.execution_id and query.work_id:
        raise HTTPException(422, msg("workflow.selectASingleSourceForThe"))
    if query.execution_id:
        execution, task = owned_execution(db, query.execution_id, user.id, team_id=team_id)
        if task.version_id != form.version_id:
            raise HTTPException(404, msg("workflow.runNotFound"))
        form = replay_defaults(form, execution.input_values)
    if query.work_id:
        work = readable_work(db, query.work_id, user.id, team_id=team_id)
        if work.version_id != form.version_id:
            raise HTTPException(404, msg("work.notFound"))
        form = replay_defaults(form, work.input_values)
        form.shared_assets = [asset_read(asset) for asset in work_assets(db, work.id)]
    form.parameter_controls = parameter_controls_for(form.fields)
    form.max_asset_bytes = config.max_asset_bytes
    return localize_form(normalize_float_defaults(form), language, version=version)


@router.put(
    "/workflows/{workflow_id}/versions/{version_id}/parameter-layout",
)
def save_workflow_parameter_layout(
    workflow_id: str,
    version_id: str,
    body: WorkflowParameterLayoutUpdate,
    db: DB,
    user: CurrentUser,
    team: TeamEditor,
) -> list[WorkflowParameterDisplay]:
    team_id = team.team.id if team else None
    workflow = owned_workflow(db, workflow_id, user.id, team_id=team_id)
    version = readable_version(db, workflow, version_id, user.id, team_id=team_id)
    machine = (
        form_machine(db, body.machine_id, user.id, team_id=team_id)
        if worker_type(version.worker_kind).connection != "platform" and body.machine_id
        else None
    )
    saved = update_parameter_layout(version, machine, body.parameter_layout)
    if team:
        team.record(db, "workflow.parametersChanged", version.id)
    db.commit()
    return saved


# scope 为 public（已发布）、mine（本人）、favorites（收藏）。后两项需要会话。
# sort 为 updated（更新时间）或 popular（先按收藏数）。每页返回列表及可选下一页游标。
# author 按作者账号名筛选，用于查看某位作者公开的全部工作流。
@router.get("/workflows")
def list_workflows(
    db: DB,
    team: TeamReader,
    viewer_id: WorkspaceReader,
    language: Language,
    session: MaybeSession,
    scope: Literal["public", "mine", "favorites"] = "public",
    category: WorkflowCategoryFilter = "all",
    search: Annotated[str, Query(max_length=120)] = "",
    author: Annotated[str, Query(max_length=32)] = "",
    public_team_id: UUID | None = None,
    project_id: UUID | None = None,
    inpaint_artifact_id: UUID | None = None,
    sort: Literal["updated", "popular"] = "updated",
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> WorkflowPage:
    query = select(Workflow).where(Workflow.visible())
    team_id = team.team.id if team else None
    if inpaint_artifact_id is not None:
        if not session or viewer_id != session.user_id:
            raise HTTPException(403, msg("workflow.signInToContinue"))
        targets = inpaint_targets(db, session.user_id, team_id, language, str(inpaint_artifact_id))
        query = query.where(Workflow.id.in_({target.workflow_id for target in targets}))
        # Match machines in the active workspace, then browse the ordinary public catalog.
        if scope == "public":
            team_id = None
    public = team_id is None and scope == "public"
    if public_team_id:
        if not public:
            raise HTTPException(422, msg("team.publicFilterRequiresCatalog"))
        query = query.where(from_public_team(Workflow.team_id, str(public_team_id)))
    if project_id:
        if scope != "mine":
            raise HTTPException(422, msg("project.workspaceFilterRequired"))
        if viewer_id is None:
            raise HTTPException(401, msg("workflow.signInToContinue"))
        project = scoped_project(db, str(project_id), viewer_id, team_id)
        query = query.where(
            project_workflow_scope(project),
            Workflow.id.in_(
                select(ProjectWorkflow.workflow_id).where(ProjectWorkflow.project_id == project.id)
            ),
        )
    elif team_id is not None:
        if scope == "favorites":
            query = query.where(
                team_visible_workflow(team_id), Workflow.id.in_(favorite_workflow_ids(team_id))
            )
        else:
            query = query.where(Workflow.team_id == team_id)
    elif public:
        query = query.where(public_catalog_workflow())
    else:
        if viewer_id is None:
            raise HTTPException(401, msg("workflow.signInToContinue"))
        if scope == "mine":
            query = query.where(
                workspace_records(Workflow.owner_id, Workflow.team_id, viewer_id, None)
            )
        else:
            query = query.where(
                Workflow.id.in_(favorite_workflow_ids(None, viewer_id)),
                or_(
                    workspace_records(Workflow.owner_id, Workflow.team_id, viewer_id, None),
                    Workflow.publicly_visible(),
                ),
            )
    if category != "all":
        query = query.where(Workflow.category == category)
    if text := search.strip():
        matching_version = WorkflowVersion.id == Workflow.published_version_id
        if not public and viewer_id is not None:
            own = workspace_records(Workflow.owner_id, Workflow.team_id, viewer_id, team_id)
            matching_version = WorkflowVersion.id == browse_version_id(own)
        query = query.where(
            or_(
                Workflow.name.icontains(text, autoescape=True),
                exists().where(
                    WorkflowVersion.workflow_id == Workflow.id,
                    matching_version,
                    WorkflowVersion.translations[language]["name"]
                    .as_string()
                    .icontains(text, autoescape=True),
                ),
            )
        )
    if author.strip():
        query = query.where(
            Workflow.owner_id.in_(select(User.id).where(User.username == author.strip()))
        )
    position = decode_cursor(cursor, 3)
    if sort == "popular":
        favorites = favorite_workflow_ids(team_id).subquery()
        count = (
            select(func.count())
            .select_from(favorites)
            .where(favorites.c.workflow_id == Workflow.id)
            .correlate(Workflow)
            .scalar_subquery()
        )
        if position:
            query = query.where(tuple_(count, Workflow.updated_at, Workflow.id) < tuple(position))
        query = query.order_by(count.desc())
    elif position:
        query = query.where(tuple_(Workflow.updated_at, Workflow.id) < tuple(position[1:]))
    records = db.scalars(
        query.order_by(Workflow.updated_at.desc(), Workflow.id.desc()).limit(limit + 1)
    ).all()

    stats = workflow_stats(db, records, team_id)
    items, next_cursor = split_page(
        records,
        limit,
        lambda last: (stats[last.id][0] if sort == "popular" else 0, last.updated_at, last.id),
    )
    covers = workflow_covers(db, items, None if public else viewer_id, team_id=team_id)
    profiles = public_team_identities(db, (item.team_id for item in items if item.published))
    return WorkflowPage(
        items=[
            workflow_read(
                item,
                covers.get(item.id),
                visible_version(item, viewer_id, public=public, team_id=team_id),
                stats[item.id],
                language=language,
                public_team=profiles.get(item.team_id) if item.team_id else None,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


def workflow_uploader(
    request: Request,
    db: DB,
    config: Config,
    session: MaybeSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> tuple[User, bool]:
    if is_official_worker(config, credentials):
        owner = db.scalar(
            select(User).where(User.username == config.official_owner, User.deleted_at.is_(None))
        )
        if owner is None:
            raise HTTPException(403, msg("workflow.notFound"))
        return owner, True
    user = current_user(session)
    check_origin(request, config)
    return protect_write(request, user, None, csrf_token), False


@router.post("/workflows", status_code=201)
def create_workflow(
    body: WorkflowCreate,
    db: DB,
    config: Config,
    uploader: Annotated[tuple[User, bool], Depends(workflow_uploader)],
    language: Language,
    initialize: Annotated[bool, Query(include_in_schema=False)] = False,
) -> WorkflowRead:
    user, service = uploader
    official = is_service_manifest(body.graph)
    if initialize and not service:
        raise HTTPException(403, msg("workflow.notFound"))
    if service and (not official or body.graph.get("workerKind") != OFFICIAL.kind):
        raise HTTPException(403, msg("workflow.notFound"))
    if official:
        require_official_import(db, user, config)
    try:
        workflow, version = import_workflow(db, user, body, initialize=initialize)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("workflow.theWorkflowChangedRefreshAndTry")) from None
    return workflow_read(workflow, version=version, language=language)


@router.post("/teams/{team_id}/workflows", status_code=201)
def create_team_workflow(
    team_id: UUID, body: WorkflowCreate, db: DB, user: LockedWriter, language: Language
) -> WorkflowRead:
    team = team_editor(team_id, db, user)
    workflow, version = import_workflow(db, user, body, team_id=team.team.id)
    db.flush()
    team.record(db, "workflow.created", workflow.id)
    db.commit()
    return workflow_read(workflow, version=version, language=language)


@router.post("/teams/{team_id}/workflows/{workflow_id}/copy", status_code=201)
def copy_workflow_to_team(
    team_id: UUID,
    workflow_id: str,
    db: DB,
    user: LockedWriter,
    language: Language,
    version_id: str | None = None,
) -> WorkflowRead:
    team = team_editor(team_id, db, user)
    source = owned_workflow(db, workflow_id, team.actor_id)
    version = readable_version(db, source, version_id, team.actor_id)
    workflow = copy_team_workflow(db, source, version, team.team.id, team.actor_id)
    team.record(db, "workflow.copied", workflow.id)
    db.commit()
    return version_workflow_read(
        db, workflow, workflow.versions[-1], team.actor_id, language, team_id=team.team.id
    )


@router.put(
    "/worker/official/workflow-covers/{sha256}",
    status_code=204,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_workflow_default_cover(
    sha256: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")],
    request: Request,
    db: DB,
    config: Config,
    uploader: Annotated[tuple[User, bool], Depends(workflow_uploader)],
    workflow_id: Annotated[UUID, Query()],
) -> Response:
    owner, service = uploader
    if not service:
        raise HTTPException(403, msg("workflow.notFound"))
    owner_id = owner.id
    await run_in_threadpool(db.rollback)
    await upload_media(
        request,
        db,
        config,
        config.max_asset_bytes,
        lambda media, stored: store_official_workflow_cover(
            db, owner_id, str(workflow_id), media, stored
        ),
        expected_hash=sha256,
    )
    return Response(status_code=204)


@router.get(
    "/workflows/{workflow_id}/cover/{sha256}/thumbnail",
    response_class=Response,
    responses=THUMBNAIL_RESPONSES,
)
async def workflow_cover_thumbnail(
    workflow_id: str,
    sha256: str,
    request: Request,
    db: DB,
    session: MaybeSession,
    config: Config,
    size: Annotated[int | None, Query(ge=1, le=MAX_THUMBNAIL_SIZE)] = None,
) -> Response:
    media = await run_in_threadpool(
        readable_workflow_cover, db, workflow_id, session.user_id if session else None, sha256
    )
    return await thumbnail_response(request, media, config, size)


@router.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    db: DB,
    team: TeamReader,
    viewer_id: WorkspaceReader,
    language: Language,
    version_id: str | None = None,
) -> WorkflowRead:
    team_id = team.team.id if team else None
    workflow = readable_workflow(db, workflow_id, viewer_id, team_id=team_id)
    version = readable_version(db, workflow, version_id, viewer_id, team_id=team_id)
    return version_workflow_read(db, workflow, version, viewer_id, language, team_id=team_id)


@router.get("/workflows/{workflow_id}/versions")
def list_workflow_versions(
    workflow_id: str, db: DB, viewer_id: WorkspaceReader, team: TeamReader
) -> WorkflowVersions:
    team_id = team.team.id if team else None
    workflow = readable_workflow(db, workflow_id, viewer_id, team_id=team_id)
    return WorkflowVersions(
        current_version_id=visible_version(workflow, viewer_id, team_id=team_id).id,
        items=[
            WorkflowVersionRead(id=version.id, number=version.number, published=version.published)
            for version in reversed(workflow.versions)
            if version.published or can_read_workflow_drafts(workflow, viewer_id, team_id)
        ],
    )


# 下载工作流文件需要登录。私有版本须有相应的读取权限。
@router.get("/workflows/{workflow_id}/graph")
def get_graph(
    workflow_id: str,
    db: DB,
    team: TeamReader,
    viewer_id: SignedInWorkspaceReader,
    version_id: str | None = None,
) -> GraphRead:
    team_id = team.team.id if team else None
    workflow = readable_workflow(db, workflow_id, viewer_id, team_id=team_id)
    version = readable_version(db, workflow, version_id, viewer_id, team_id=team_id)
    return GraphRead(version_id=version.id, graph=workflow_graph(workflow, version))


@router.patch("/workflows/{workflow_id}")
def update_workflow(
    workflow_id: str, body: WorkflowUpdate, db: DB, user: Writer, config: Config, language: Language
) -> WorkflowRead:
    workflow = owned_workflow(db, workflow_id, user.id)
    if body.graph is not None and (is_service_manifest(body.graph) or workflow.official_key):
        require_official_import(db, user, config)
    apply_workflow_update(workflow, body)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg("workflow.theWorkflowChangedRefreshAndTry")) from None
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id, language)


@router.patch("/teams/{team_id}/workflows/{workflow_id}")
def update_team_workflow(
    team_id: UUID,
    workflow_id: str,
    body: WorkflowUpdate,
    db: DB,
    user: LockedWriter,
    language: Language,
) -> WorkflowRead:
    team = team_editor(team_id, db, user)
    workflow = owned_workflow(db, workflow_id, team.actor_id, team_id=team.team.id)
    if body.graph is not None and is_service_manifest(body.graph):
        raise HTTPException(422, msg("team.comfyuiImport"))
    apply_workflow_update(workflow, body)
    team.record(db, "workflow.updated", workflow.id)
    db.commit()
    return version_workflow_read(
        db, workflow, workflow.versions[-1], team.actor_id, language, team_id=team.team.id
    )


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, db: DB, user: CurrentUser, team: TeamManager) -> Response:
    workflow = owned_workflow(
        db, workflow_id, user.id, team_id=team.team.id if team else None, include_deleted=True
    )
    if workflow.mark_deleted():
        if team:
            team.record(db, "workflow.deleted", workflow.id)
        db.commit()
    return Response(status_code=204)


# 撤销删除。工作流恢复原来的发布状态，关联作品随之恢复可见。
@router.post("/workflows/{workflow_id}/restore")
def restore_workflow(
    workflow_id: str, db: DB, user: CurrentUser, team: TeamManager, language: Language
) -> WorkflowRead:
    team_id = team.team.id if team else None
    workflow = owned_workflow(db, workflow_id, user.id, team_id=team_id, include_deleted=True)
    if workflow.restore():
        if team:
            team.record(db, "workflow.restored", workflow.id)
        db.commit()
    return version_workflow_read(
        db, workflow, workflow.versions[-1], user.id, language, team_id=team_id
    )


@router.post("/workflows/{workflow_id}/publish")
def publish_workflow(
    workflow_id: str, db: DB, user: CurrentUser, team: TeamManager, language: Language
) -> WorkflowRead:
    team_id = team.team.id if team else None
    workflow = owned_workflow(db, workflow_id, user.id, team_id=team_id)
    version = workflow.versions[-1]
    success = db.scalar(
        select(
            exists().where(
                workspace_records(Task.owner_id, Task.team_id, user.id, team_id),
                Task.version_id == version.id,
                exists().where(Execution.task_id == Task.id, Execution.status == Status.SUCCEEDED),
            )
        )
    )
    if not success:
        raise HTTPException(409, msg("workflow.runThisVersionSuccessfullyBeforePublishing"))
    workflow.published = True
    version.published = True
    workflow.published_version_id = version.id
    workflow.updated_at = now_ms()
    if team:
        team.record(db, "workflow.published", workflow.id)
    db.commit()
    return version_workflow_read(db, workflow, version, user.id, language, team_id=team_id)


@router.put("/workflows/{workflow_id}/cover")
def set_workflow_cover(
    workflow_id: str, body: WorkflowCoverUpdate, db: DB, user: Writer, language: Language
) -> WorkflowRead:
    workflow = update_workflow_cover(db, workflow_id, user.id, body)
    db.commit()
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id, language)


@router.put("/teams/{team_id}/workflows/{workflow_id}/cover")
def set_team_workflow_cover(
    team_id: UUID,
    workflow_id: str,
    body: WorkflowCoverUpdate,
    db: DB,
    user: LockedWriter,
    language: Language,
) -> WorkflowRead:
    team = team_editor(team_id, db, user)
    workflow = update_workflow_cover(db, workflow_id, team.actor_id, body, team_id=team.team.id)
    team.record(db, "workflow.coverChanged", workflow.id)
    db.commit()
    return version_workflow_read(
        db, workflow, workflow.versions[-1], team.actor_id, language, team_id=team.team.id
    )


@router.put("/workflows/{workflow_id}/favorite", status_code=204)
def favorite_workflow(workflow_id: str, db: DB, user: Writer) -> Response:
    readable_workflow(db, workflow_id, user.id)
    if not db.get(Favorite, (user.id, workflow_id)):
        db.add(Favorite(user_id=user.id, workflow_id=workflow_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return Response(status_code=204)


@router.delete("/workflows/{workflow_id}/favorite", status_code=204)
def unfavorite_workflow(workflow_id: str, db: DB, user: Writer) -> Response:
    favorite = db.get(Favorite, (user.id, workflow_id))
    if favorite:
        db.delete(favorite)
        db.commit()
    return Response(status_code=204)


@router.put("/teams/{team_id}/workflows/{workflow_id}/favorite", status_code=204)
def favorite_team_workflow(team_id: UUID, workflow_id: str, db: DB, user: LockedWriter) -> Response:
    team = team_editor(team_id, db, user)
    workflow = readable_workflow(db, workflow_id, team.actor_id, team_id=team.team.id)
    if db.get(TeamFavorite, (team.team.id, workflow.id)) is None:
        db.add(
            TeamFavorite(team_id=team.team.id, workflow_id=workflow.id, added_by_id=team.actor_id)
        )
        team.record(db, "favorite.added", workflow.id)
        db.commit()
    return Response(status_code=204)


@router.delete("/teams/{team_id}/workflows/{workflow_id}/favorite", status_code=204)
def unfavorite_team_workflow(
    team_id: UUID, workflow_id: str, db: DB, user: LockedWriter
) -> Response:
    team = team_editor(team_id, db, user)
    if favorite := db.get(TeamFavorite, (team.team.id, workflow_id)):
        db.delete(favorite)
        team.record(db, "favorite.removed", workflow_id)
        db.commit()
    return Response(status_code=204)


@router.get("/workspace")
def workspace(db: DB, user: CurrentUser, config: Config, team: TeamReader) -> WorkspaceRead:
    if team is not None:
        ids = db.scalars(
            select(Workflow.id).where(
                Workflow.id.in_(favorite_workflow_ids(team.team.id)),
                team_visible_workflow(team.team.id),
                Workflow.visible(),
            )
        ).all()
        return WorkspaceRead(
            favorite_ids=list(ids),
            can_import_official_workflows=False,
            can_manage_official_import_grants=False,
        )
    ids = db.scalars(
        select(Workflow.id).where(
            Workflow.id.in_(favorite_workflow_ids(None, user.id)),
            Workflow.visible(),
            or_(
                workspace_records(Workflow.owner_id, Workflow.team_id, user.id, None),
                Workflow.publicly_visible(),
            ),
        )
    ).all()
    return WorkspaceRead(
        favorite_ids=list(ids),
        can_import_official_workflows=can_import_official_workflows(user, config),
        can_manage_official_import_grants=config.is_official_owner(user.username),
    )
