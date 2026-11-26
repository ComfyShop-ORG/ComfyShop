"""验证 ComfyUI 图格式，按访问者选择可读取的工作流版本与封面。"""

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from comfyshop_worker_protocol.definition import WorkerDefinition
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import ColumnElement, Select, case, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from comfyshop_api.core.i18n import SOURCE_LANGUAGE, msg
from comfyshop_api.db import write_lock
from comfyshop_api.models import (
    Artifact,
    Execution,
    Favorite,
    MediaObject,
    OfficialWorkflowCover,
    Status,
    Task,
    TeamFavorite,
    User,
    Work,
    Workflow,
    WorkflowVersion,
    now_ms,
)
from comfyshop_api.schemas import (
    AuthorRead,
    FieldWorkflow,
    MediaRead,
    PublicTeamIdentity,
    ServiceManifest,
    WorkflowCoverUpdate,
    WorkflowCreate,
    WorkflowRead,
    WorkflowUpdate,
)
from comfyshop_api.security import owned_record, workspace_records
from comfyshop_api.services.covers import checked_cover_image, cover_from_asset
from comfyshop_api.services.inputs import (
    official_input,
    parameter_layout_for,
    validated_parameter_layout,
)
from comfyshop_api.services.media_records import artifact_media, cover_image_read
from comfyshop_api.services.originals import attach_original
from comfyshop_api.services.public_catalog import (
    OFFICIAL_SOURCE_PREFIX,
    public_catalog_workflow,
    public_work_condition,
)
from comfyshop_api.services.public_teams import public_team_identities
from comfyshop_api.services.teams import find_team
from comfyshop_api.services.worker_types import OFFICIAL, PERSONAL, route, worker_type
from comfyshop_api.services.workspace_shares import has_workspace_share
from comfyshop_media.uploads import ReceivedMedia


def browse_version_id(own: ColumnElement[bool]) -> ColumnElement[str]:
    latest = (
        select(WorkflowVersion.id)
        .where(WorkflowVersion.workflow_id == Workflow.id)
        .order_by(WorkflowVersion.number.desc())
        .limit(1)
        .correlate(Workflow)
        .scalar_subquery()
    )
    return case((own, latest), else_=Workflow.published_version_id)


def parse_graph(graph: dict) -> tuple[Literal["api", "ui"], str, list[str]]:
    """返回图格式、内容哈希和排序后的节点类型。

    `api` 是可提交执行的格式，`ui` 是 ComfyUI 编辑器格式。
    无效图返回 HTTP 422，序列化后超过 5 MiB 返回 413。
    """
    try:
        encoded = json.dumps(
            graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (ValueError, TypeError):
        raise HTTPException(422, msg("workflow.invalidData")) from None
    if len(encoded) > 5 * 1024 * 1024:
        raise HTTPException(413, msg("workflow.tooLarge"))
    is_ui = isinstance(graph.get("nodes"), list)
    nodes = graph["nodes"] if is_ui else list(graph.values())
    kind_key = "type" if is_ui else "class_type"
    if (
        not nodes
        or len(nodes) > 5000
        or not all(
            isinstance(node, dict)
            and isinstance(node.get(kind_key), str)
            and node[kind_key]
            and (is_ui or isinstance(node.get("inputs"), dict))
            for node in nodes
        )
    ):
        raise HTTPException(422, msg("workflow.uploadAComfyuiWorkflowOrApi"))
    requirements = sorted({node[kind_key] for node in nodes})
    return "ui" if is_ui else "api", hashlib.sha256(encoded).hexdigest(), requirements


def team_visible_workflow(team_id: str) -> ColumnElement[bool]:
    return (Workflow.team_id == team_id) | public_catalog_workflow()


def readable_workflow(
    db: Session,
    workflow_id: str,
    user_id: str | None,
    *,
    allow_shared_media: bool = False,
    team_id: str | None = None,
) -> Workflow:
    if team_id is not None:
        workflow = db.scalar(
            select(Workflow).where(
                Workflow.id == workflow_id, Workflow.visible(), team_visible_workflow(team_id)
            )
        )
        if workflow is None:
            raise HTTPException(404, msg("workflow.notFound"))
        return workflow
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        raise HTTPException(404, msg("workflow.notFound"))
    if workflow.team_id is not None:
        if workflow.published and db.scalar(
            select(Workflow.id).where(Workflow.id == workflow_id, Workflow.publicly_visible())
        ):
            return workflow
        if allow_shared_media and find_team(db, workflow.team_id, user_id) is not None:
            return workflow
        raise HTTPException(404, msg("workflow.notFound"))
    if (
        not workflow.published
        and workflow.owner_id != user_id
        and not (allow_shared_media and has_workspace_share(db, workflow.owner_id, user_id))
    ):
        raise HTTPException(404, msg("workflow.notFound"))
    return workflow


def owned_workflow(
    db: Session,
    workflow_id: str,
    user_id: str,
    *,
    include_deleted: bool = False,
    team_id: str | None = None,
) -> Workflow:
    workflow = owned_record(
        db, Workflow, workflow_id, user_id, msg("workflow.notFound"), team_id=team_id
    )
    if workflow.deleted_at is not None and not include_deleted:
        raise HTTPException(404, msg("workflow.notFound"))
    return workflow


def can_read_workflow_drafts(
    workflow: Workflow, viewer_id: str | None, team_id: str | None
) -> bool:
    return workflow.team_id == team_id and (team_id is not None or workflow.owner_id == viewer_id)


def visible_version(
    workflow: Workflow, viewer_id: str | None, *, public: bool = False, team_id: str | None = None
) -> WorkflowVersion:
    """为作者选择最新草稿，为公开浏览选择发布指针指向的版本。

    `viewer_id` 为 `None` 表示访客。`public=True` 时作者也按公开视图读取。
    缺少可用公开版本返回 HTTP 404。
    """
    if not public and can_read_workflow_drafts(workflow, viewer_id, team_id):
        return workflow.versions[-1]
    version = next((v for v in workflow.versions if v.id == workflow.published_version_id), None)
    if not workflow.published or version is None:
        raise HTTPException(404, msg("workflow.versionNotFound"))
    return version


def readable_version(
    db: Session,
    workflow: Workflow,
    version_id: str | None,
    user_id: str | None,
    *,
    team_id: str | None = None,
) -> WorkflowVersion:
    """指定版本时检查发布状态、所有者或本人执行记录，无权读取时返回 HTTP 404。"""
    if not version_id:
        return visible_version(workflow, user_id, team_id=team_id)
    version = next((v for v in workflow.versions if v.id == version_id), None)
    if version and (version.published or can_read_workflow_drafts(workflow, user_id, team_id)):
        return version
    if (
        team_id is None
        and version
        and user_id
        and db.scalar(
            select(Task.id)
            .where(Task.version_id == version.id, Task.owner_id == user_id, Task.team_id.is_(None))
            .limit(1)
        )
    ):
        return version
    raise HTTPException(404, msg("workflow.versionNotFound"))


def _public_cover_work_ids() -> Select[tuple[str]]:
    return (
        select(Work.id)
        .join(Artifact, Artifact.id == Work.cover_artifact_id)
        .where(
            Work.workflow_id == Workflow.id,
            Work.team_id.is_not_distinct_from(Workflow.team_id),
            or_(Workflow.team_id.is_not(None), Work.owner_id == Workflow.owner_id),
            public_work_condition(),
            Artifact.visible(),
        )
    )


def workflow_covers(
    db: Session, workflows: Sequence[Workflow], viewer_id: str | None, *, team_id: str | None = None
) -> dict[str, MediaRead]:
    """依次选用指定的公开作品、作者上传的图片、最近公开的作品和模型默认图。

    作者访问缺少封面的工作流时，可看到自己最近一次成功执行的成品。
    公共列表传 `None`，所有人看到相同的封面。
    """
    covers: dict[str, MediaRead] = {}
    if not workflows:
        return covers
    public = _public_cover_work_ids().correlate(Workflow)
    pinned = public.where(Work.id == Workflow.cover_work_id).scalar_subquery()
    latest = public.order_by(Work.created_at.desc(), Work.id.desc()).limit(1).scalar_subquery()
    # 有作者上传的封面时，只检查指定作品。其余从索引取最近公开的作品，不展开历史。
    choice = func.coalesce(pinned, case((Workflow.default_cover_sha256.is_(None), latest)))
    chosen = aliased(Work)
    picture = aliased(MediaObject)
    picture_sha256 = case(
        (chosen.id.is_not(None), chosen.cover_image_sha256),
        else_=func.coalesce(Workflow.default_cover_sha256, OfficialWorkflowCover.sha256),
    )
    official_key = func.coalesce(
        Workflow.official_key,
        case(
            (
                Workflow.remote_source.startswith(OFFICIAL_SOURCE_PREFIX),
                func.substr(Workflow.remote_source, len(OFFICIAL_SOURCE_PREFIX) + 1),
            )
        ),
    )
    for workflow_id, work_id, artifact, frame_ms, image in db.execute(
        select(Workflow.id, chosen.id, Artifact, chosen.cover_frame_ms, picture)
        .options(joinedload(Artifact.media, innerjoin=False))
        .select_from(Workflow)
        .outerjoin(chosen, chosen.id == choice)
        .outerjoin(Artifact, Artifact.id == chosen.cover_artifact_id)
        .outerjoin(OfficialWorkflowCover, OfficialWorkflowCover.official_key == official_key)
        .outerjoin(picture, picture.sha256 == picture_sha256)
        .where(Workflow.id.in_([workflow.id for workflow in workflows]))
    ).tuples():
        if work_id is not None and artifact is not None:
            covers[workflow_id] = cover_image_read("works", work_id, image) or artifact_media(
                artifact, frame_ms
            )
        elif cover := cover_image_read("workflows", workflow_id, image):
            covers[workflow_id] = cover
    private_ids = [
        workflow.id
        for workflow in workflows
        if workflow.id not in covers and can_read_workflow_drafts(workflow, viewer_id, team_id)
    ]
    if private_ids:
        # 从这个工作流自己的任务出发找执行。状态条件若能走索引，查询计划会沿全平台的
        # 成功执行逐条比对工作流，没有结果的工作流要扫完全部记录。状态拼接空串后
        # 不再匹配索引，只作为过滤条件，SQLite 和 PostgreSQL 都适用。
        own_tasks = (
            select(Task.id)
            .where(
                Task.workflow_id == Workflow.id,
                workspace_records(Task.owner_id, Task.team_id, viewer_id, team_id),
            )
            .correlate(Workflow)
        )
        private = (
            select(Artifact.id)
            .join(Execution, Execution.id == Artifact.execution_id)
            .where(
                Execution.task_id.in_(own_tasks),
                Execution.status.concat("") == Status.SUCCEEDED,
                Artifact.visible(),
            )
            .order_by(
                Execution.created_at.desc(),
                Execution.id.desc(),
                Artifact.content_type.startswith("image/").desc(),
                Artifact.output_index,
                Artifact.id,
            )
            .limit(1)
            .correlate(Workflow)
            .scalar_subquery()
        )
        # 私有封面同样批量读取，列表中的工作流数量不会增加查询次数。
        for workflow_id, artifact in db.execute(
            select(Workflow.id, Artifact)
            .join(Artifact, Artifact.id == private)
            .where(Workflow.id.in_(private_ids))
        ).tuples():
            covers[workflow_id] = artifact_media(artifact)
    return covers


def update_workflow_cover(
    db: Session,
    workflow_id: str,
    owner_id: str,
    body: WorkflowCoverUpdate,
    *,
    team_id: str | None = None,
) -> Workflow:
    workflow = owned_workflow(db, workflow_id, owner_id, team_id=team_id)
    write_lock(db, Workflow, workflow.id)
    db.refresh(workflow)
    if workflow.deleted_at is not None:
        raise HTTPException(404, msg("workflow.notFound"))
    if body.asset_id is not None:
        workflow.default_cover_sha256 = cover_from_asset(
            db, body.asset_id, owner_id, team_id=team_id
        ).sha256
    elif body.work_id is not None and not db.scalar(
        _public_cover_work_ids()
        .where(Workflow.id == workflow.id, Work.id == body.work_id)
        .with_for_update(of=Work, read=True)
    ):
        raise HTTPException(404, msg("workflow.chooseOneOfYourPublicWorks"))
    workflow.cover_work_id = body.work_id
    return workflow


def store_official_workflow_cover(
    db: Session, owner_id: str, workflow_id: str, media: ReceivedMedia, stored: bool
) -> tuple[None, bool]:
    """为指定的官方工作流登记默认图。"""
    if not media.content_type.startswith("image/"):
        raise HTTPException(422, msg("media.theCoverMustBeAnImage"))
    try:
        write_lock(db, User, owner_id)
        key = db.scalar(
            select(Workflow.official_key)
            .where(
                Workflow.id == workflow_id,
                Workflow.owner_id == owner_id,
                Workflow.official_key.is_not(None),
                Workflow.visible(),
            )
            .with_for_update(of=Workflow)
        )
        if key is None:
            raise HTTPException(404, msg("workflow.notFound"))
        image = attach_original(db, media, stored)
        cover = db.get(OfficialWorkflowCover, key)
        if cover is None:
            db.add(OfficialWorkflowCover(official_key=key, sha256=image.sha256))
        else:
            cover.sha256 = image.sha256
        db.commit()
        return None, image.storage_name == media.path.name
    except BaseException:
        db.rollback()
        raise


def readable_workflow_cover(
    db: Session, workflow_id: str, viewer_id: str | None, sha256: str
) -> MediaObject:
    workflow = readable_workflow(db, workflow_id, viewer_id, allow_shared_media=True)
    cover_sha256 = workflow.default_cover_sha256
    key = workflow.official_key
    if (
        key is None
        and workflow.remote_source
        and workflow.remote_source.startswith(OFFICIAL_SOURCE_PREFIX)
    ):
        key = workflow.remote_source.removeprefix(OFFICIAL_SOURCE_PREFIX)
    if cover_sha256 != sha256 and key:
        cover = db.get(OfficialWorkflowCover, key)
        cover_sha256 = cover.sha256 if cover else None
    image = db.get(MediaObject, sha256) if cover_sha256 == sha256 else None
    return checked_cover_image(db, image, sha256)


def favorite_workflow_ids(team_id: str | None, user_id: str | None = None) -> Select[tuple[str]]:
    if team_id is not None:
        return select(TeamFavorite.workflow_id).where(TeamFavorite.team_id == team_id)
    query = select(Favorite.workflow_id)
    return query if user_id is None else query.where(Favorite.user_id == user_id)


def workflow_stats(
    db: Session, workflows: Sequence[Workflow], team_id: str | None
) -> dict[str, tuple[int, int]]:
    """按工作流 ID 返回空间内的收藏数和成功完成的任务数。"""
    ids = [workflow.id for workflow in workflows]
    if not ids:
        return {}
    favorite_rows = favorite_workflow_ids(team_id).subquery()
    favorites: dict[str, int] = dict(
        db.execute(
            select(favorite_rows.c.workflow_id, func.count())
            .where(favorite_rows.c.workflow_id.in_(ids))
            .group_by(favorite_rows.c.workflow_id)
        )
        .tuples()
        .all()
    )
    runs: dict[str, int] = dict(
        db.execute(
            select(Task.workflow_id, func.count())
            .where(
                Task.workflow_id.in_(ids), Task.status == Status.SUCCEEDED, Task.team_id == team_id
            )
            .group_by(Task.workflow_id)
        )
        .tuples()
        .all()
    )
    return {
        workflow_id: (favorites.get(workflow_id, 0), runs.get(workflow_id, 0))
        for workflow_id in ids
    }


def workflow_read(
    workflow: Workflow,
    media: MediaRead | None = None,
    version: WorkflowVersion | None = None,
    stats: tuple[int, int] = (0, 0),
    *,
    language: str = SOURCE_LANGUAGE,
    public_team: PublicTeamIdentity | None = None,
) -> WorkflowRead:
    version = version or workflow.versions[-1]
    name, description = workflow_text(workflow, version, language)
    popularity, runs = stats
    published = workflow.deleted_at is None and workflow.published and version.published
    return WorkflowRead(
        id=workflow.id,
        name=name,
        author=workflow.owner.username,
        author_profile=AuthorRead.from_user(workflow.owner),
        owner=workflow.owner_id,
        team_id=workflow.team_id,
        public_team=public_team if published else None,
        category=workflow.category,
        published=published,
        version_id=version.id,
        version=version.number,
        worker=route(version.worker_kind, version.connection_scope),
        format=version.format,
        graph_hash=version.graph_hash,
        requirements=version.requirements,
        updated=workflow.updated_at,
        media=media,
        cover_work_id=workflow.cover_work_id,
        description=description or "",
        popularity=popularity,
        runs=runs,
    )


def workflow_text(
    workflow: Workflow, version: WorkflowVersion, language: str
) -> tuple[str, str | None]:
    """保留作者写入的标题和简介，按当前语言展示官方清单的译文。"""
    texts = version.translations or {}
    text = texts.get(language) or texts.get(SOURCE_LANGUAGE, {})
    name = workflow.name
    description = workflow.description
    if _uses_manifest_text(workflow, "name", name):
        name = text.get("name", name)
    if _uses_manifest_text(workflow, "description", description):
        description = text.get("description", description)
    return name, description


def _uses_manifest_text(workflow: Workflow, field: str, value: str | None) -> bool:
    return any(
        entry.get(field) == value for entry in (workflow.versions[-1].translations or {}).values()
    )


def version_workflow_read(
    db: Session,
    workflow: Workflow,
    version: WorkflowVersion,
    viewer_id: str | None,
    language: str,
    *,
    team_id: str | None = None,
) -> WorkflowRead:
    profiles = public_team_identities(db, [workflow.team_id]) if version.published else {}
    return workflow_read(
        workflow,
        workflow_covers(db, [workflow], viewer_id, team_id=team_id).get(workflow.id),
        version,
        workflow_stats(db, [workflow], team_id)[workflow.id],
        language=language,
        public_team=profiles.get(workflow.team_id) if workflow.team_id else None,
    )


def replay_workflow_read(
    db: Session,
    workflow_id: str,
    version_id: str,
    user_id: str,
    language: str,
    *,
    team_id: str | None = None,
) -> WorkflowRead:
    """按生成表单的权限读取重跑来源。归档或不可访问的来源返回 404。"""
    try:
        workflow = readable_workflow(db, workflow_id, user_id, team_id=team_id)
        version = readable_version(db, workflow, version_id, user_id, team_id=team_id)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        raise HTTPException(404, msg("workflow.couldNotLoadParametersBecauseThe")) from None
    return version_workflow_read(db, workflow, version, user_id, language, team_id=team_id)


def is_service_manifest(graph: dict) -> bool:
    return graph.get("format") == "service"


def manifest_worker(spec: ServiceManifest) -> WorkerDefinition:
    worker = worker_type(spec.worker_kind)
    if worker.connection != "platform" or worker.form != "fields":
        raise HTTPException(422, msg("workflow.invalidData"))
    return worker


def field_graph(spec: FieldWorkflow, worker: WorkerDefinition) -> tuple[dict, str]:
    fields = [official_input(field) for field in spec.fields]
    if len({f.id for f in fields}) != len(fields) or any(
        f.kind not in worker.input_kinds for f in fields
    ):
        raise HTTPException(422, msg("workflow.invalidData"))
    if not {spec.execution.output_kind, *spec.execution.additional_output_kinds} <= set(
        worker.output_kinds
    ):
        raise HTTPException(422, msg("output.invalidOutputKind"))
    layout = validated_parameter_layout(fields, spec.parameter_layout)
    graph = spec.model_dump(mode="json", by_alias=False, include={"fields", "execution"})
    if layout:
        graph["parameter_layout"] = [
            entry.model_dump(mode="json", exclude_none=True) for entry in layout
        ]
    graph = _without_display_text(graph)
    return graph, _field_graph_hash(graph)


def _without_display_text(graph: dict) -> dict:
    """从执行定义中去掉名称、帮助和选项文案，保留实际取值和参数布局。"""
    canonical = {
        **graph,
        "fields": [
            {key: value for key, value in field.items() if key not in {"label", "choice_labels"}}
            for field in graph["fields"]
        ],
    }
    if layout := graph.get("parameter_layout"):
        canonical["parameter_layout"] = [
            {key: value for key, value in entry.items() if key not in {"display_name", "help"}}
            for entry in layout
        ]
    return canonical


def _field_graph_hash(graph: dict) -> str:
    encoded = json.dumps(graph, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > 256 * 1024:
        raise HTTPException(413, msg("workflow.tooLarge"))
    return hashlib.sha256(encoded).hexdigest()


def _manifest_translations(definition: ServiceManifest) -> dict:
    translations = {
        code: text.model_dump(mode="json", exclude_none=True)
        for code, text in definition.translations.items()
    }
    translations.setdefault(
        SOURCE_LANGUAGE,
        {
            "name": definition.name,
            "description": definition.description,
            "fields": {
                field.name: field.model_dump(include={"label", "choice_labels"}, exclude_none=True)
                for field in definition.fields
            },
            "parameter_layout": {
                row.field_id: row.model_dump(include={"display_name", "help"}, exclude_none=True)
                for row in definition.parameter_layout
                if row.display_name or row.help
            },
        },
    )
    if len(json.dumps(translations, ensure_ascii=False).encode()) > 512 * 1024:
        raise HTTPException(413, msg("workflow.tooLarge"))
    return translations


def import_workflow(
    db: Session,
    owner: User,
    body: WorkflowCreate,
    *,
    initialize: bool = False,
    team_id: str | None = None,
) -> tuple[Workflow, WorkflowVersion]:
    definition = _service_manifest(body.graph) if is_service_manifest(body.graph) else None
    workflow = None
    identity = None
    if definition:
        if team_id is not None:
            raise HTTPException(422, msg("team.comfyuiImport"))
        identity = definition.source_identity
        condition = (
            Workflow.official_key == definition.key
            if definition.worker_kind == OFFICIAL.kind
            else Workflow.remote_source == identity
        )
        workflow = db.scalar(select(Workflow).where(condition, Workflow.team_id.is_(None)))
        if workflow and workflow.owner_id != owner.id:
            raise HTTPException(409, msg("grants.keyInUse"))
        if workflow and workflow.deleted_at is not None:
            raise HTTPException(409, msg("workflow.theWorkflowChangedRefreshAndTry"))
    if workflow is None:
        workflow = Workflow(
            owner=owner,
            team_id=team_id,
            official_key=definition.key
            if definition and definition.worker_kind == OFFICIAL.kind
            else None,
            remote_source=identity,
            name=body.name,
            category=body.category,
            description=definition.description if definition else None,
        )
        db.add(workflow)
    elif definition is not None:
        name = body.name if _uses_manifest_text(workflow, "name", workflow.name) else workflow.name
        description = (
            definition.description
            if "description" in definition.model_fields_set
            and _uses_manifest_text(workflow, "description", workflow.description)
            else workflow.description
        )
        if workflow.name != name or workflow.description != description:
            workflow.name = name
            workflow.description = description
            workflow.updated_at = now_ms()
    version = new_version(workflow, body.graph, definition=definition)
    if initialize and definition is not None:
        db.flush()
        if not workflow.published or workflow.published_version_id != version.id:
            workflow.updated_at = now_ms()
        version.published = workflow.published = True
        workflow.published_version_id = version.id
    return workflow, version


def append_workflow_version(
    workflow: Workflow, graph: dict, graph_hash: str, version: WorkflowVersion
) -> WorkflowVersion:
    """Attach the normalized graph as the next version of this workflow."""
    version.number = workflow.versions[-1].number + 1 if workflow.versions else 1
    version.graph = graph
    version.graph_hash = graph_hash
    workflow.versions.append(version)
    return version


def copy_team_workflow(
    db: Session, source: Workflow, version: WorkflowVersion, team_id: str, actor_id: str
) -> Workflow:
    workflow = Workflow(
        owner_id=actor_id,
        team_id=team_id,
        name=source.name,
        category=source.category,
        description=source.description,
        remote_source=source.remote_source,
        default_cover_sha256=source.default_cover_sha256,
    )
    append_workflow_version(
        workflow,
        version.graph,
        version.graph_hash,
        WorkflowVersion(
            translations=version.translations,
            parameter_layout=version.parameter_layout,
            worker_kind=version.worker_kind,
            connection_scope=version.connection_scope,
            worker_data=version.worker_data,
            format=version.format,
            requirements=version.requirements,
        ),
    )
    db.add(workflow)
    db.flush()
    return workflow


def _service_manifest(graph: dict) -> ServiceManifest:
    try:
        definition = ServiceManifest.model_validate(graph)
    except ValidationError:
        raise HTTPException(422, msg("workflow.invalidData")) from None
    if not definition.name.strip() or len({field.name for field in definition.fields}) != len(
        definition.fields
    ):
        raise HTTPException(422, msg("workflow.invalidData"))
    by_name = {field.name: field for field in definition.fields}
    layout = {entry.field_id for entry in definition.parameter_layout}
    for text in definition.translations.values():
        if text.fields.keys() - by_name.keys() or text.parameter_layout.keys() - layout:
            raise HTTPException(422, msg("workflow.invalidData"))
        for name, field in text.fields.items():
            if field.choice_labels and (
                by_name[name].kind != "choice"
                or field.choice_labels.keys()
                - {value for value in by_name[name].choices if isinstance(value, str)}
            ):
                raise HTTPException(422, msg("workflow.invalidData"))
    return definition


def apply_workflow_update(workflow: Workflow, body: WorkflowUpdate) -> None:
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, msg("workflow.enterAName"))
        workflow.name = body.name.strip()
    if body.category is not None:
        workflow.category = body.category
    if body.description is not None:
        workflow.description = body.description.strip() or None
    if body.graph is not None:
        new_version(workflow, body.graph)
    workflow.updated_at = now_ms()


def new_version(
    workflow: Workflow, graph: dict, *, definition: ServiceManifest | None = None
) -> WorkflowVersion:
    format_: Literal["api", "ui", "service", "remote"]
    requirements: list[str]
    translations = None
    if is_service_manifest(graph):
        definition = definition or _service_manifest(graph)
        if workflow.remote_source != definition.source_identity:
            raise HTTPException(422, msg("workflow.invalidData"))
        graph, graph_hash = field_graph(definition, manifest_worker(definition))
        translations = _manifest_translations(definition)
        prior = next(
            (
                version
                for version in reversed(workflow.versions)
                if version.graph_hash == graph_hash
                or (
                    version.format == "service"
                    and _field_graph_hash(_without_display_text(version.graph)) == graph_hash
                )
            ),
            None,
        )
        if prior is not None:
            prior.translations = (prior.translations or {}) | translations
            return prior
        format_, requirements = "service", []
        workflow.updated_at = now_ms()
    else:
        if workflow.remote_source is not None:
            raise HTTPException(422, msg("workflow.invalidData"))
        format_, graph_hash, requirements = parse_graph(graph)
    return append_workflow_version(
        workflow,
        graph,
        graph_hash,
        WorkflowVersion(
            translations=translations,
            worker_kind=definition.worker_kind if definition else PERSONAL.kind,
            format=format_,
            requirements=requirements,
        ),
    )


def workflow_graph(workflow: Workflow, version: WorkflowVersion) -> dict:
    if worker_type(version.worker_kind).connection != "platform":
        return version.graph
    layout = parameter_layout_for(version)
    assert workflow.remote_source is not None
    translations = version.translations or {}
    source = translations.get(SOURCE_LANGUAGE, {})
    fields = [
        field | source.get("fields", {}).get(field["name"], {}) for field in version.graph["fields"]
    ]
    if version.parameter_layout is None:
        layout = [
            entry.model_copy(update=source.get("parameter_layout", {}).get(entry.field_id, {}))
            for entry in layout
        ]
    else:
        # The saved layout replaces the manifest layout, including author-written text.
        authored = {
            entry.field_id: entry.model_dump(include={"display_name", "help"}, exclude_none=True)
            for entry in layout
            if entry.display_name or entry.help
        }
        translations = {
            code: text | {"parameter_layout": authored} for code, text in translations.items()
        }
    return ServiceManifest.model_validate(
        {
            "format": "service",
            "worker_kind": version.worker_kind,
            "key": workflow.remote_source.rsplit(":", 1)[1],
            "name": workflow.name,
            "category": workflow.category,
            "description": workflow.description,
            **version.graph,
            "fields": fields,
            "parameter_layout": layout,
            "translations": translations,
        }
    ).model_dump(
        mode="json",
        by_alias=True,
        exclude={
            key
            for key, value in (("parameter_layout", layout), ("translations", translations))
            if not value
        },
    )
