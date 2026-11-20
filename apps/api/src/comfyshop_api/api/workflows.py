"""工作流接口，提供导入、版本浏览、表单、发布以及封面和示例管理。"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import exists, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError

from comfyshop_api.core.categories import WorkflowCategoryFilter
from comfyshop_api.models import (
    Status,
    Execution,
    Favorite,
    Machine,
    Task,
    User,
    Work,
    Workflow,
    now_ms,
)
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    GraphRead,
    WorkflowCoverUpdate,
    WorkflowCreate,
    WorkflowPage,
    WorkflowRead,
    WorkflowUpdate,
    WorkflowVersionRead,
    WorkflowVersions,
    WorkspaceRead,
    WorkflowForm,
    WorkflowInputQuery,
    WorkflowParameterDisplay,
    WorkflowParameterLayoutUpdate,
)
from comfyshop_api.security import CurrentUser, DB, Writer, MaybeSession, owned_record
from comfyshop_api.services.workflows import (
    new_version,
    owned_workflow,
    readable_workflow,
    workflow_read,
    workflow_covers,
    workflow_stats,
    readable_version,
    version_workflow_read,
    visible_version,
)
from comfyshop_api.services.inputs import (
    form_for,
    normalize_float_defaults,
    parameter_controls_for,
    replay_defaults,
    update_parameter_layout,
)
from comfyshop_api.services.executions import owned_execution
from comfyshop_api.services.media_records import asset_read
from comfyshop_api.services.works import readable_work, work_assets

router = APIRouter(tags=["workflows"])


def form_machine(db: DB, machine_id: str, user_id: str) -> Machine:
    machine = owned_record(db, Machine, machine_id, user_id, "工作机不存在")
    if machine.revoked_at:
        raise HTTPException(404, "工作机不存在")
    return machine


@router.get("/workflows/{workflow_id}/inputs", response_model=WorkflowForm)
def workflow_inputs(
    workflow_id: str,
    db: DB,
    user: CurrentUser,
    query: Annotated[WorkflowInputQuery, Query()],
) -> WorkflowForm:
    workflow = readable_workflow(db, workflow_id, user.id)
    version = readable_version(db, workflow, query.version_id, user.id)
    machine = form_machine(db, query.machine_id, user.id)
    form = form_for(version, machine, include_original_defaults=workflow.owner_id == user.id)
    if query.execution_id and query.work_id:
        raise HTTPException(422, "只能指定一个重跑来源")
    if query.execution_id:
        execution, task = owned_execution(db, query.execution_id, user.id)
        if task.version_id != version.id:
            raise HTTPException(404, "执行不存在")
        form = replay_defaults(form, execution.input_values)
    if query.work_id:
        work = readable_work(db, query.work_id, user.id)
        if work.version_id != version.id:
            raise HTTPException(404, "作品不存在")
        form = replay_defaults(form, work.input_values)
        form.shared_assets = [asset_read(asset) for asset in work_assets(db, work.id)]
    form.parameter_controls = parameter_controls_for(form.fields)
    return normalize_float_defaults(form)


@router.put(
    "/workflows/{workflow_id}/versions/{version_id}/parameter-layout",
    response_model=list[WorkflowParameterDisplay],
)
def save_workflow_parameter_layout(
    workflow_id: str,
    version_id: str,
    body: WorkflowParameterLayoutUpdate,
    db: DB,
    user: Writer,
) -> list[WorkflowParameterDisplay]:
    workflow = owned_workflow(db, workflow_id, user.id)
    version = readable_version(db, workflow, version_id, user.id)
    machine = form_machine(db, body.machine_id, user.id)
    saved = update_parameter_layout(version, machine, body.parameter_layout)
    db.commit()
    return saved


# scope 为 public（已发布）、mine（本人）、favorites（收藏）。后两项需要会话。
# sort 为 updated（更新时间）或 popular（先按收藏数）。每页返回列表及可选下一页游标。
# author 按作者账号名筛选，用于查看某位作者公开的全部工作流。
@router.get("/workflows", response_model=WorkflowPage)
def list_workflows(
    db: DB,
    session: MaybeSession,
    scope: Literal["public", "mine", "favorites"] = "public",
    category: WorkflowCategoryFilter = "all",
    search: str = Query(default="", max_length=120),
    author: str = Query(default="", max_length=32),
    sort: Literal["updated", "popular"] = "updated",
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=24, ge=1, le=100),
) -> WorkflowPage:
    query = select(Workflow).where(Workflow.visible())
    if scope == "public":
        query = query.where(Workflow.published.is_(True))
    else:
        if not session:
            raise HTTPException(401, "请先登录")
        if scope == "mine":
            query = query.where(Workflow.owner_id == session.user_id)
        else:
            query = (
                query.join(Favorite)
                .where(Favorite.user_id == session.user_id)
                .where(or_(Workflow.owner_id == session.user_id, Workflow.published.is_(True)))
            )
    if category != "all":
        query = query.where(Workflow.in_category(category))
    if search.strip():
        query = query.where(Workflow.name.contains(search.strip(), autoescape=True))
    if author.strip():
        query = query.where(
            Workflow.owner_id.in_(select(User.id).where(User.username == author.strip()))
        )
    count = (
        select(func.count())
        .select_from(Favorite)
        .where(Favorite.workflow_id == Workflow.id)
        .correlate(Workflow)
        .scalar_subquery()
    )
    position = decode_cursor(cursor, 3)
    if sort == "popular":
        if position:
            query = query.where(tuple_(count, Workflow.updated_at, Workflow.id) < tuple(position))
        query = query.order_by(count.desc())
    elif position:
        query = query.where(tuple_(Workflow.updated_at, Workflow.id) < tuple(position[1:]))
    records = db.scalars(
        query.order_by(Workflow.updated_at.desc(), Workflow.id.desc()).limit(limit + 1)
    ).all()

    def cursor_position(last: Workflow) -> tuple[int, int, str]:
        popularity = db.scalars(
            select(func.count()).select_from(Favorite).where(Favorite.workflow_id == last.id)
        ).one()
        return popularity if sort == "popular" else 0, last.updated_at, last.id

    items, next_cursor = split_page(records, limit, cursor_position)
    viewer_id = session.user_id if session else None
    covers = workflow_covers(db, items, None if scope == "public" else viewer_id)
    stats = workflow_stats(db, items)
    return WorkflowPage(
        items=[
            workflow_read(
                item,
                covers.get(item.id),
                visible_version(item, viewer_id, public=scope == "public"),
                stats[item.id],
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.post("/workflows", response_model=WorkflowRead, status_code=201)
def create_workflow(body: WorkflowCreate, db: DB, user: Writer) -> WorkflowRead:
    workflow = Workflow(owner_id=user.id, owner=user, name=body.name, category=body.category)
    new_version(workflow, body.graph)
    db.add(workflow)
    db.commit()
    return workflow_read(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: str, db: DB, session: MaybeSession, version_id: str | None = None
) -> WorkflowRead:
    viewer_id = session.user_id if session else None
    workflow = readable_workflow(db, workflow_id, viewer_id)
    version = readable_version(db, workflow, version_id, viewer_id)
    return version_workflow_read(db, workflow, version, viewer_id)


@router.get("/workflows/{workflow_id}/versions", response_model=WorkflowVersions)
def list_workflow_versions(workflow_id: str, db: DB, session: MaybeSession) -> WorkflowVersions:
    viewer_id = session.user_id if session else None
    workflow = readable_workflow(db, workflow_id, viewer_id)
    return WorkflowVersions(
        current_version_id=visible_version(workflow, viewer_id).id,
        items=[
            WorkflowVersionRead(id=version.id, number=version.number, published=version.published)
            for version in reversed(workflow.versions)
            if version.published or workflow.owner_id == viewer_id
        ],
    )


# 下载工作流文件需要登录。公开工作流对所有登录账号开放，私有工作流只对作者开放。
@router.get("/workflows/{workflow_id}/graph", response_model=GraphRead)
def get_graph(
    workflow_id: str, db: DB, user: CurrentUser, version_id: str | None = None
) -> GraphRead:
    workflow = readable_workflow(db, workflow_id, user.id)
    version = readable_version(db, workflow, version_id, user.id)
    return GraphRead(version_id=version.id, graph=version.graph)


@router.patch("/workflows/{workflow_id}", response_model=WorkflowRead)
def update_workflow(workflow_id: str, body: WorkflowUpdate, db: DB, user: Writer) -> WorkflowRead:
    workflow = owned_workflow(db, workflow_id, user.id)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, "名称不能为空")
        workflow.name = body.name.strip()
    if body.category is not None:
        workflow.category = body.category
    if body.description is not None:
        workflow.description = body.description.strip() or None
    if body.graph is not None:
        new_version(workflow, body.graph)
    workflow.updated_at = now_ms()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "工作流已更新，请刷新后重试") from None
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id)


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, db: DB, user: Writer) -> Response:
    workflow = owned_record(db, Workflow, workflow_id, user.id, "工作流不存在")
    if workflow.mark_deleted():
        db.commit()
    return Response(status_code=204)


# 撤销删除。工作流恢复原来的发布状态，关联作品随之恢复可见。
@router.post("/workflows/{workflow_id}/restore", response_model=WorkflowRead)
def restore_workflow(workflow_id: str, db: DB, user: Writer) -> WorkflowRead:
    workflow = owned_record(db, Workflow, workflow_id, user.id, "工作流不存在")
    if workflow.restore():
        db.commit()
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id)


@router.post("/workflows/{workflow_id}/publish", response_model=WorkflowRead)
def publish_workflow(workflow_id: str, db: DB, user: Writer) -> WorkflowRead:
    workflow = owned_workflow(db, workflow_id, user.id)
    success = db.scalar(
        select(
            exists().where(
                Task.owner_id == user.id,
                Task.version_id == workflow.versions[-1].id,
                exists().where(Execution.task_id == Task.id, Execution.status == Status.SUCCEEDED),
            )
        )
    )
    if not success:
        raise HTTPException(409, "当前版本需要一次成功记录")
    workflow.published = True
    workflow.versions[-1].published = True
    workflow.published_version_id = workflow.versions[-1].id
    workflow.updated_at = now_ms()
    db.commit()
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id)


# 作者从自己在此工作流下公开的作品里指定封面，传 null 恢复为取最近公开的作品。
@router.put("/workflows/{workflow_id}/cover", response_model=WorkflowRead)
def set_workflow_cover(
    workflow_id: str, body: WorkflowCoverUpdate, db: DB, user: Writer
) -> WorkflowRead:
    workflow = owned_workflow(db, workflow_id, user.id)
    if body.work_id is not None:
        work = db.get(Work, body.work_id)
        if (
            not work
            or work.owner_id != user.id
            or work.workflow_id != workflow.id
            or not work.published
            or work.deleted_at is not None
        ):
            raise HTTPException(404, "请选择自己在此工作流下公开的作品")
    workflow.cover_work_id = body.work_id
    db.commit()
    return version_workflow_read(db, workflow, workflow.versions[-1], user.id)


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


@router.get("/workspace", response_model=WorkspaceRead)
def workspace(db: DB, user: CurrentUser) -> WorkspaceRead:
    ids = db.scalars(
        select(Workflow.id)
        .join(Favorite)
        .where(
            Favorite.user_id == user.id,
            Workflow.visible(),
            or_(Workflow.owner_id == user.id, Workflow.published.is_(True)),
        )
    ).all()
    return WorkspaceRead(favorite_ids=list(ids))
