"""验证 ComfyUI 图格式，按访问者选择可读取的工作流版本与封面。"""

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from comfyshop_api.models import (
    MediaObject,
    Artifact,
    Execution,
    Favorite,
    Status,
    Task,
    Work,
    Workflow,
    WorkflowVersion,
)
from comfyshop_api.schemas import MediaRead, WorkflowRead
from comfyshop_api.services.media_records import artifact_media
from comfyshop_api.services.works import public_work_condition


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
        raise HTTPException(422, "工作流包含无效数据") from None
    if len(encoded) > 5 * 1024 * 1024:
        raise HTTPException(413, "工作流不能超过 5 MB")
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
        raise HTTPException(422, "请上传 ComfyUI 工作流或 API JSON")
    requirements = sorted({node[kind_key] for node in nodes})
    return "ui" if is_ui else "api", hashlib.sha256(encoded).hexdigest(), requirements


def readable_workflow(db: Session, workflow_id: str, user_id: str | None) -> Workflow:
    workflow = db.get(Workflow, workflow_id)
    if (
        not workflow
        or workflow.deleted_at
        or (not workflow.published and workflow.owner_id != user_id)
    ):
        raise HTTPException(404, "工作流不存在")
    return workflow


def owned_workflow(db: Session, workflow_id: str, user_id: str) -> Workflow:
    workflow = readable_workflow(db, workflow_id, user_id)
    if workflow.owner_id != user_id:
        raise HTTPException(404, "工作流不存在")
    return workflow


def visible_version(
    workflow: Workflow, viewer_id: str | None, *, public: bool = False
) -> WorkflowVersion:
    """为作者选择最新草稿，为公开浏览选择发布指针指向的版本。

    `viewer_id` 为 `None` 表示访客。`public=True` 时作者也按公开视图读取。
    缺少可用公开版本返回 HTTP 404。
    """
    if workflow.owner_id == viewer_id and not public:
        return workflow.versions[-1]
    version = next((v for v in workflow.versions if v.id == workflow.published_version_id), None)
    if not workflow.published or version is None:
        raise HTTPException(404, "工作流版本不存在")
    return version


def readable_version(
    db: Session, workflow: Workflow, version_id: str | None, user_id: str | None
) -> WorkflowVersion:
    """指定版本时检查发布状态、所有者或本人执行记录，无权读取时返回 HTTP 404。"""
    if not version_id:
        return visible_version(workflow, user_id)
    version = next((v for v in workflow.versions if v.id == version_id), None)
    if version and (workflow.owner_id == user_id or version.published):
        return version
    if (
        version
        and user_id
        and db.scalar(
            select(Task.id).where(Task.version_id == version.id, Task.owner_id == user_id).limit(1)
        )
    ):
        return version
    raise HTTPException(404, "工作流版本不存在")


def workflow_covers(
    db: Session, workflows: Sequence[Workflow], viewer_id: str | None
) -> dict[str, MediaRead]:
    """按工作流 ID 返回封面：作者指定的公开作品封面，未指定时取作者最近公开的作品。

    `viewer_id` 是作者本人时，还没有公开作品的工作流使用其最近一次成功执行的首张成品，
    这张封面只有作者能看到。公共列表传 `None`，所有人看到相同的封面。
    """
    # 封面成品，以及它是视频时所选画面的时间点。
    covers: dict[str, tuple[Artifact, int | None]] = {}
    if not workflows:
        return {}
    public = (
        select(Work.id)
        .join(Artifact, Artifact.id == Work.cover_artifact_id)
        .where(
            Work.workflow_id == Workflow.id,
            Work.owner_id == Workflow.owner_id,
            public_work_condition(),
            Artifact.visible(),
        )
        .correlate(Workflow)
    )
    pinned = public.where(Work.id == Workflow.cover_work_id).scalar_subquery()
    latest = public.order_by(Work.created_at.desc(), Work.id.desc()).limit(1).scalar_subquery()
    # 每个工作流只返回一个成品；最新公开作品可沿复合索引取首项，不展开历史作品。
    # 封面跟随那件作品自己的封面，包括作者为视频选定的画面。
    chosen = aliased(Work)
    for workflow_id, artifact, frame_ms in db.execute(
        select(Workflow.id, Artifact, chosen.cover_frame_ms)
        .select_from(Workflow)
        .join(chosen, chosen.id == func.coalesce(pinned, latest))
        .join(Artifact, Artifact.id == chosen.cover_artifact_id)
        .where(Workflow.id.in_([workflow.id for workflow in workflows]))
    ).tuples():
        covers[workflow_id] = (artifact, frame_ms)
    private_ids = [
        workflow.id
        for workflow in workflows
        if workflow.id not in covers and workflow.owner_id == viewer_id
    ]
    if private_ids:
        # 从这个工作流自己的任务出发找执行。状态条件若能走索引，查询计划会沿全平台的
        # 成功执行逐条比对工作流，没有结果的工作流要扫完全部记录。状态拼接空串后
        # 不再匹配索引，只作为过滤条件，SQLite 和 PostgreSQL 都适用。
        own_tasks = (
            select(Task.id)
            .where(Task.workflow_id == Workflow.id, Task.owner_id == Workflow.owner_id)
            .correlate(Workflow)
        )
        private = (
            select(Artifact.id)
            .join(Execution, Execution.id == Artifact.execution_id)
            .join(Artifact.media)
            .where(
                Execution.task_id.in_(own_tasks),
                Execution.status.concat("") == Status.SUCCEEDED,
                Artifact.visible(),
            )
            .order_by(
                Execution.created_at.desc(),
                Execution.id.desc(),
                MediaObject.content_type.startswith("image/").desc(),
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
            covers[workflow_id] = (artifact, None)
    return {
        workflow_id: artifact_media(artifact, frame_ms)
        for workflow_id, (artifact, frame_ms) in covers.items()
    }


def workflow_stats(db: Session, workflows: Sequence[Workflow]) -> dict[str, tuple[int, int]]:
    """按工作流 ID 返回（收藏数，成功完成的任务数），两项都统计所有账号。"""
    ids = [workflow.id for workflow in workflows]
    if not ids:
        return {}
    favorites: dict[str, int] = dict(
        db.execute(
            select(Favorite.workflow_id, func.count())
            .where(Favorite.workflow_id.in_(ids))
            .group_by(Favorite.workflow_id)
        )
        .tuples()
        .all()
    )
    runs: dict[str, int] = dict(
        db.execute(
            select(Task.workflow_id, func.count())
            .where(Task.workflow_id.in_(ids), Task.status == Status.SUCCEEDED)
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
) -> WorkflowRead:
    version = version or workflow.versions[-1]
    return WorkflowRead(
        id=workflow.id,
        name=workflow.name,
        author=workflow.owner.username,
        owner=workflow.owner_id,
        category=workflow.category,
        published=workflow.deleted_at is None and workflow.published and version.published,
        version_id=version.id,
        version=version.number,
        format=version.format,
        graph_hash=version.graph_hash,
        requirements=version.requirements,
        updated=workflow.updated_at,
        media=media,
        cover_work_id=workflow.cover_work_id,
        description=workflow.description or "",
        popularity=stats[0],
        runs=stats[1],
    )


def version_workflow_read(
    db: Session, workflow: Workflow, version: WorkflowVersion, viewer_id: str | None
) -> WorkflowRead:
    return workflow_read(
        workflow,
        workflow_covers(db, [workflow], viewer_id).get(workflow.id),
        version,
        workflow_stats(db, [workflow])[workflow.id],
    )


def replay_workflow_read(
    db: Session, workflow_id: str, version_id: str, user_id: str
) -> WorkflowRead:
    """按生成表单的权限读取重跑来源。归档或不可访问的来源返回 404。"""
    try:
        workflow = readable_workflow(db, workflow_id, user_id)
        version = readable_version(db, workflow, version_id, user_id)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        raise HTTPException(404, "来源工作流或版本不可用，无法载入参数") from None
    return version_workflow_read(db, workflow, version, user_id)


def new_version(workflow: Workflow, graph: dict) -> WorkflowVersion:
    format_, graph_hash, requirements = parse_graph(graph)
    number = workflow.versions[-1].number + 1 if workflow.versions else 1
    version = WorkflowVersion(
        number=number,
        graph=graph,
        graph_hash=graph_hash,
        format=format_,
        requirements=requirements,
    )
    workflow.versions.append(version)
    return version
