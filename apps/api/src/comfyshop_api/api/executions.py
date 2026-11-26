from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, tuple_

from comfyshop_api.api.teams import TeamEditor, TeamReader
from comfyshop_api.api.workspace_shares import SignedInWorkspaceReader
from comfyshop_api.core.i18n import Language, msg
from comfyshop_api.models import Artifact, Execution, Status, Task
from comfyshop_api.pagination import decode_cursor, split_page
from comfyshop_api.schemas import (
    CoverUpdate,
    ExecutionPage,
    ExecutionRead,
    ReplayRead,
)
from comfyshop_api.security import DB, Config, CurrentUser, workspace_records
from comfyshop_api.services.artifacts import (
    delete_result_artifacts,
    restore_result_artifacts,
)
from comfyshop_api.services.assets import ensure_quota_for_restore
from comfyshop_api.services.covers import readable_execution_cover, update_execution_cover
from comfyshop_api.services.executions import execution_reads, owned_execution
from comfyshop_api.services.media_responses import THUMBNAIL_RESPONSES, thumbnail_response
from comfyshop_api.services.projects import active_project_id, scoped_project
from comfyshop_api.services.workflows import replay_workflow_read
from comfyshop_media.renditions import MAX_THUMBNAIL_SIZE

router = APIRouter(prefix="/executions", tags=["executions"])

MAX_DATE_MS = 8_640_000_000_000_000


@router.get("")
def list_executions(
    db: DB,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
    workflow_id: str | None = None,
    version_id: str | None = None,
    task_id: str | None = None,
    project_id: UUID | None = None,
    workflow_name: Annotated[str | None, Query(max_length=120)] = None,
    created_from: Annotated[
        int | None,
        Query(
            ge=-MAX_DATE_MS,
            le=MAX_DATE_MS,
            description="执行创建时间的起点，含该时刻（Unix 毫秒）。",
        ),
    ] = None,
    created_before: Annotated[
        int | None,
        Query(
            ge=-MAX_DATE_MS,
            le=MAX_DATE_MS,
            description="执行创建时间的终点，不含该时刻（Unix 毫秒）。",
        ),
    ] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> ExecutionPage:
    members = select(Artifact.id).where(Artifact.execution_id == Execution.id).correlate(Execution)
    query = (
        select(Execution, Task)
        .join(Task, Task.id == Execution.task_id)
        .where(
            workspace_records(
                Task.owner_id, Task.team_id, owner_id, team.team.id if team else None
            ),
            Execution.status == Status.SUCCEEDED,
            # 只收起因删除而空的结果组。历史执行的状态与输入仍可读取。
            ~members.where(Artifact.deleted_at.is_not(None)).exists()
            | members.where(Artifact.visible()).exists(),
        )
    )
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if version_id:
        query = query.where(Task.version_id == version_id)
    if task_id:
        query = query.where(Task.id == task_id)
    if project_id:
        project = scoped_project(db, str(project_id), owner_id, team.team.id if team else None)
        query = query.where(Task.project_id == project.id)
    if text := (workflow_name or "").strip():
        query = query.where(Task.workflow_name.icontains(text, autoescape=True))
    if created_from is not None:
        query = query.where(Execution.created_at >= created_from)
    if created_before is not None:
        query = query.where(Execution.created_at < created_before)
    position = decode_cursor(cursor, 2)
    if position:
        query = query.where(tuple_(Execution.created_at, Execution.id) < tuple(position))
    records = db.execute(
        query.order_by(Execution.created_at.desc(), Execution.id.desc()).limit(limit + 1)
    ).all()
    items, next_cursor = split_page(records, limit, lambda row: (row[0].created_at, row[0].id))
    return ExecutionPage(items=execution_reads(db, items), next_cursor=next_cursor)


@router.get("/{execution_id}")
def get_execution(
    execution_id: str,
    db: DB,
    user: CurrentUser,
    team: TeamReader,
    owner_id: SignedInWorkspaceReader,
) -> ExecutionRead:
    execution, task = owned_execution(
        db, execution_id, owner_id, team_id=team.team.id if team else None
    )
    result = execution_reads(db, [(execution, task)])[0]
    if owner_id != user.id and (execution.status != Status.SUCCEEDED or not result.artifact_count):
        raise HTTPException(404, msg("workflow.runNotFound"))
    return result


@router.delete("/{execution_id}/artifacts", status_code=204)
def delete_execution_artifacts(
    execution_id: str, db: DB, user: CurrentUser, team: TeamEditor
) -> Response:
    execution, _ = owned_execution(
        db, execution_id, user.id, team_id=team.team.id if team else None
    )
    delete_result_artifacts(db, execution)
    if team:
        team.record(db, "execution.outputsDeleted", execution.id)
    db.commit()
    return Response(status_code=204)


# 撤销最近一次整组删除。
@router.post("/{execution_id}/artifacts/restore")
def restore_execution_artifacts(
    execution_id: str, db: DB, user: CurrentUser, team: TeamEditor, config: Config
) -> ExecutionRead:
    execution, task = owned_execution(
        db, execution_id, user.id, team_id=team.team.id if team else None
    )
    # 已删除任务的成品恢复后，任务的素材重新计入配额。
    ensure_quota_for_restore(db, task, config)
    restore_result_artifacts(db, execution)
    if team:
        team.record(db, "execution.outputsRestored", execution.id)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


@router.put("/{execution_id}/cover")
def set_execution_cover(
    execution_id: str,
    body: CoverUpdate,
    db: DB,
    user: CurrentUser,
    team: TeamEditor,
    config: Config,
) -> ExecutionRead:
    execution, task = update_execution_cover(
        db, execution_id, user.id, body, config, team_id=team.team.id if team else None
    )
    if team:
        team.record(db, "execution.coverChanged", execution.id)
    db.commit()
    return execution_reads(db, [(execution, task)])[0]


@router.get(
    "/{execution_id}/cover/{sha256}/thumbnail",
    response_class=Response,
    responses=THUMBNAIL_RESPONSES,
)
async def execution_cover_thumbnail(
    execution_id: str,
    sha256: str,
    request: Request,
    db: DB,
    user: CurrentUser,
    config: Config,
    size: Annotated[int | None, Query(ge=1, le=MAX_THUMBNAIL_SIZE)] = None,
) -> Response:
    media = await run_in_threadpool(readable_execution_cover, db, execution_id, user.id, sha256)
    return await thumbnail_response(request, media, config, size)


@router.get("/{execution_id}/replay")
def replay_execution(
    execution_id: str, db: DB, user: CurrentUser, team: TeamReader, language: Language
) -> ReplayRead:
    team_id = team.team.id if team else None
    execution, task = owned_execution(db, execution_id, user.id, team_id=team_id)
    return ReplayRead(
        workflow=replay_workflow_read(
            db, task.workflow_id, task.version_id, user.id, language, team_id=team_id
        ),
        source_execution_id=execution.id,
        project_id=active_project_id(db, task.project_id),
    )
